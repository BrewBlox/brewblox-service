"""
Offers event publishing and subscription for service implementations.

Example use:

    events.setup(app)

    async def on_message(subscription, key, message):
        logging.info(f'Message from {subscription}: {key} = {message} ({type(message)})')

    listener = events.get_listener(app)
    listener.subscribe('brewblox', 'controller', on_message=on_message)
    listener.subscribe('brewblox', 'controller.*', on_message=on_message)
    listener.subscribe('brewblox', 'controller.#', on_message=on_message)

    publisher = events.get_publisher(app)
    await publisher.publish('brewblox', 'controller.value', {'example': True})

"""

import asyncio
import json
from concurrent.futures import CancelledError, TimeoutError
from datetime import timedelta
from typing import Callable, List, Union

import aioamqp
from aiohttp import web
from brewblox_service import brewblox_logger, features

LOGGER = brewblox_logger(__name__)
routes = web.RouteTableDef()

EVENT_CALLBACK_ = Callable[['EventSubscription', str, Union[dict, str]], None]
ExchangeType_ = str

EVENTBUS_HOST = 'eventbus'
EVENTBUS_PORT = 5672
RECONNECT_INTERVAL = timedelta(seconds=1)
PENDING_WAIT_TIMEOUT = timedelta(seconds=5)


def setup(app: web.Application):
    features.add(app, EventListener(app))
    features.add(app, EventPublisher(app))
    app.router.add_routes(routes)


def get_listener(app: web.Application) -> 'EventListener':
    return features.get(app, EventListener)


def get_publisher(app: web.Application) -> 'EventPublisher':
    return features.get(app, EventPublisher)


##############################################################################
# Incoming events
##############################################################################

async def _default_on_message(sub: 'EventSubscription', key: str, message: Union[dict, str]):
    LOGGER.info(f'Unhandled event: subscription={sub}, key={key}, message={message}')


class EventSubscription():
    def __init__(self,
                 exchange_name: str,
                 routing: str,
                 exchange_type: ExchangeType_='topic',
                 on_message: EVENT_CALLBACK_=None):
        self._routing = routing
        self._exchange_name = exchange_name
        self._exchange_type = exchange_type
        self.on_message = on_message

    def __str__(self):
        return f'<{self._routing} @ {self._exchange_name}>'

    @property
    def on_message(self) -> EVENT_CALLBACK_:
        return self._on_message

    @on_message.setter
    def on_message(self, f: EVENT_CALLBACK_):
        self._on_message = f if f else _default_on_message

    async def declare_on_remote(self, channel: aioamqp.channel.Channel):
        LOGGER.info(f'Declaring event bus subscription {self} on {channel}')

        await channel.exchange_declare(
            exchange_name=self._exchange_name,
            type_name=self._exchange_type,
            auto_delete=True
        )

        queue_info = await channel.queue_declare(exclusive=True)
        queue_name = queue_info['queue']

        await channel.queue_bind(
            queue_name=queue_name,
            exchange_name=self._exchange_name,
            routing_key=self._routing
        )

        await channel.basic_consume(
            callback=self._relay,
            queue_name=queue_name
        )

    async def _relay(self,
                     channel: aioamqp.channel.Channel,
                     body: str,
                     envelope: aioamqp.envelope.Envelope,
                     properties: aioamqp.properties.Properties):
        """Relays incoming messages between the queue and the user callback"""
        try:
            await self.on_message(self, envelope.routing_key, json.loads(body))
        except Exception as ex:
            LOGGER.error(f'Exception relaying message in {self}: {ex}')


class EventListener(features.ServiceFeature):
    def __init__(self, app: web.Application=None, host: str=EVENTBUS_HOST):
        super().__init__(app)

        self._host: str = host

        # Asyncio queues need a context loop
        # We'll initialize self._pending when we have one
        self._pending_pre_async: List[EventSubscription] = []
        self._pending: asyncio.Queue = None
        self._subscriptions: List[EventSubscription] = []

        self._loop: asyncio.BaseEventLoop = None
        self._task: asyncio.Task = None

    def __str__(self):
        return f'<{type(self).__name__} {self._host}>'

    async def startup(self, app: web.Application):
        # Initialize the async queue now we know which loop we're using
        self._loop = app.loop
        self._pending = asyncio.Queue(loop=self._loop)

        # Transfer all subscriptions that were made before the event loop started
        [self._pending.put_nowait(s) for s in self._pending_pre_async]

        # We won't be needing this anymore
        self._pending_pre_async = None

        self._lazy_listen()

    async def shutdown(self, *_):
        LOGGER.info(f'Closing {self}')

        try:
            self._task.cancel()
            await self._task
        except Exception:
            pass
        finally:
            self._task = None

    def subscribe(self,
                  exchange_name: str,
                  routing: str,
                  exchange_type: ExchangeType_='topic',
                  on_message: EVENT_CALLBACK_=None):
        """Adds a new event subscription to the listener.

        Actual queue declaration to the remote message server is done when connected.
        If the listener is not currently connected, it defers declaration.

        on_message(queue, key, message) can be specified.
        If the event was in JSON, message is a dict. Otherwise it is a string

        If on_message() is not set, it will default to logging the message.
        """
        sub = EventSubscription(
            exchange_name,
            routing,
            exchange_type,
            on_message=on_message
        )

        if self._pending is not None:
            self._pending.put_nowait(sub)
        else:
            self._pending_pre_async.append(sub)
            LOGGER.info(f'Deferred event bus subscription: [{sub}]')

        self._lazy_listen()
        return sub

    def _lazy_listen(self):
        """
        Ensures that the listener task only runs when actually needed.
        This function is a noop if any of the preconditions is not met.

        Preconditions are:
        * An asyncio eventloop is available (self._loop)
        * The task is not already running
        * There are subscriptions: either pending, or active
        """
        if all([
            self._loop,
            not self._task,
            self._subscriptions or (self._pending and not self._pending.empty()),
        ]):
            self._task = self._loop.create_task(self._listen())

    async def _listen(self):
        retrying = False

        while True:
            try:
                transport, protocol = await aioamqp.connect(
                    host=self._host,
                    loop=self._loop
                )

                channel = await protocol.channel()

                LOGGER.info(f'Connected {self}')

                # Declare all current subscriptions if reconnecting
                [await sub.declare_on_remote(channel) for sub in self._subscriptions]

                while True:
                    subscription = None

                    try:
                        await protocol.ensure_open()
                        retrying = False

                        subscription = await asyncio.wait_for(
                            self._pending.get(),
                            timeout=PENDING_WAIT_TIMEOUT.seconds
                        )

                    except TimeoutError:
                        # Timeout ensures that connection state is checked at least once per timeout
                        continue

                    try:
                        await protocol.ensure_open()
                        await subscription.declare_on_remote(channel)
                        self._subscriptions.append(subscription)

                    except Exception:
                        # Put subscription back in queue
                        # We'll declare it after reconnect
                        self._pending.put_nowait(subscription)
                        raise

            except CancelledError:
                LOGGER.info(f'Cancelled {self}')
                break

            except Exception as ex:
                if not retrying:
                    LOGGER.warn(f'Connection error in {self}: {type(ex)}:{ex}')
                    retrying = True

                await asyncio.sleep(RECONNECT_INTERVAL.seconds)
                continue

            finally:
                try:
                    await protocol.close()
                    transport.close()
                except Exception:  # pragma: no cover
                    pass


##############################################################################
# Outgoing events
##############################################################################

class EventPublisher(features.ServiceFeature):
    def __init__(self, app: web.Application=None, host: str=EVENTBUS_HOST):
        super().__init__(app)

        self._loop: asyncio.BaseEventLoop = None
        self._host: str = host
        self._reset()

    @property
    def connected(self):
        return self._transport and self._protocol and self._channel

    def __str__(self):
        return f'<{type(self).__name__} {self._host}>'

    async def startup(self, app: web.Application):
        self._loop = app.loop

    def _reset(self):
        self._transport = None
        self._protocol: aioamqp.AmqpProtocol = None
        self._channel: aioamqp.channel.Channel = None

    async def shutdown(self, *_):
        LOGGER.info(f'Closing {self}')

        try:
            await self._protocol.close()
            self._transport.close()
        except Exception:
            pass
        finally:
            self._reset()

    async def _ensure_channel(self):
        # Lazy connect
        if not self.connected:
            self._transport, self._protocol = await aioamqp.connect(
                host=self._host,
                loop=self._loop
            )
            self._channel = await self._protocol.channel()

        # Assert connection
        try:
            await self._protocol.ensure_open()
        except aioamqp.exceptions.AioamqpException:
            await self.shutdown()
            raise

    async def publish(self,
                      exchange: str,
                      routing: str,
                      message: Union[str, dict]='',
                      exchange_type: ExchangeType_='topic'):
        try:
            await self._ensure_channel()
        except Exception:
            # If server has restarted since our last attempt, ensure channel will fail (old connection invalid)
            # Retry once to check whether a new connection can be made
            await self._ensure_channel()

        # json.dumps() also correctly handles strings
        data = json.dumps(message).encode()

        await self._channel.exchange_declare(
            exchange_name=exchange,
            type_name=exchange_type,
            auto_delete=True
        )

        await self._channel.basic_publish(
            payload=data,
            exchange_name=exchange,
            routing_key=routing
        )


##############################################################################
# REST endpoints
##############################################################################

@routes.post('/_debug/publish')
async def post_publish(request):
    """
    ---
    tags:
    - Events
    summary: Publish event.
    description: Publish a new event message to the event bus.
    operationId: events.publish
    produces:
    - text/plain
    parameters:
    -
        in: body
        name: body
        description: Event message
        required: true
        schema:
            type: object
            properties:
                exchange:
                    type: string
                routing:
                    type: string
                message:
                    type: object
    """
    args = await request.json()
    try:
        await get_publisher(request.app).publish(
            args['exchange'],
            args['routing'],
            args['message']
        )
        return web.Response()

    except Exception as ex:
        LOGGER.warn(f'Unable to publish {args}: {ex}')
        return web.Response(body='Event bus connection refused', status=500)


@routes.post('/_debug/subscribe')
async def post_subscribe(request):
    """
    ---
    tags:
    - Events
    summary: Subscribe to events.
    operationId: events.subscribe
    produces:
    - text/plain
    parameters:
    -
        in: body
        name: body
        description: Event message
        required: true
        schema:
            type: object
            properties:
                exchange:
                    type: string
                routing:
                    type: string
    """
    args = await request.json()
    get_listener(request.app).subscribe(
        args['exchange'],
        args['routing']
    )
    return web.Response()
