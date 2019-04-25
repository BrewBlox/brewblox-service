"""
Offers event publishing and subscription for service implementations.

Example use:

    from brewblox_service import scheduler, events

    scheduler.setup(app)
    events.setup(app)

    async def on_message(subscription, key, message):
        print(f'Message from {subscription}: {key} = {message} ({type(message)})')

    listener = events.get_listener(app)
    listener.subscribe('brewblox', 'controller', on_message=on_message)
    listener.subscribe('brewblox', 'controller.*', on_message=on_message)
    listener.subscribe('brewblox', 'controller.#', on_message=on_message)

    publisher = events.get_publisher(app)
    await publisher.publish('brewblox', 'controller.value', {'example': True})

"""

import asyncio
import json
import warnings
from datetime import timedelta
from typing import Callable, Coroutine, List, Union

import aioamqp
from aiohttp import web

from brewblox_service import brewblox_logger, features, scheduler, strex

LOGGER = brewblox_logger(__name__)
routes = web.RouteTableDef()

EVENT_CALLBACK_ = Callable[['EventSubscription', str, Union[dict, str]], Coroutine]
ExchangeType_ = str

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
    """
    Subscription class for receiving AMQP messages.

    This class should not be instantiated directly.
    To subscribe to AMQP messages, use `EventListener.subscribe()`

    The `on_message` property can safely be changed while the subscription is active.
    It will be used for the next received message.
    """

    def __init__(self,
                 exchange_name: str,
                 routing: str,
                 exchange_type: ExchangeType_ = 'topic',
                 on_message: EVENT_CALLBACK_ = None):
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
            await channel.basic_client_ack(envelope.delivery_tag)
            await self.on_message(self, envelope.routing_key, json.loads(body))
        except Exception as ex:
            LOGGER.error(f'Exception relaying message in {self}: {ex}')


class EventListener(features.ServiceFeature):
    """
    Allows subscribing to AMQP messages published to a central event bus.

    `EventListener` will maintain a persistent connection to the AMQP host,
    and ensures that all subscriptions remain valid if the connection is lost and reestablished.
    """

    def __init__(self,
                 app: web.Application,
                 host: str = None,
                 port: int = None
                 ):
        super().__init__(app)

        self._host: str = host or app['config']['eventbus_host']
        self._port: int = port or app['config']['eventbus_port']

        # Asyncio queues need a context loop
        # We'll initialize self._pending when we have one
        self._pending_pre_async: List[EventSubscription] = []
        self._pending: asyncio.Queue = None
        self._subscriptions: List[EventSubscription] = []

        self._loop: asyncio.BaseEventLoop = None
        self._task: asyncio.Task = None

    def __str__(self):
        return f'<{type(self).__name__} for "{self._host}">'

    @property
    def running(self):
        return bool(self._task and not self._task.done())

    def _lazy_listen(self):
        """
        Ensures that the listener task only runs when actually needed.
        This function is a no-op if any of the preconditions is not met.

        Preconditions are:
        * The application is running (self._loop is set)
        * The task is not already running
        * There are subscriptions: either pending, or active
        """
        if all([
            self._loop,
            not self.running,
            self._subscriptions or (self._pending and not self._pending.empty()),
        ]):
            self._task = self._loop.create_task(self._listen())

    async def _listen(self):
        LOGGER.info(f'{self} now listening')
        retrying = False

        while True:
            try:
                transport, protocol = await aioamqp.connect(
                    host=self._host,
                    port=self._port,
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

                    except asyncio.CancelledError:
                        # Exiting task
                        raise

                    except asyncio.TimeoutError:  # pragma: no cover
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

            except asyncio.CancelledError:
                LOGGER.info(f'Cancelled {self}')
                break

            except Exception as ex:
                if not retrying:
                    warnings.warn(f'Connection error in {self}: {strex(ex)}')
                    retrying = True

                await asyncio.sleep(RECONNECT_INTERVAL.seconds)
                continue

            finally:
                try:
                    await protocol.close()
                    transport.close()
                except Exception:  # pragma: no cover
                    pass

    async def startup(self, app: web.Application):
        await self.shutdown(app)

        # Initialize the async queue now we know which loop we're using
        self._loop = asyncio.get_event_loop()
        self._pending = asyncio.Queue()

        # Transfer all subscriptions that were made before the event loop started
        [self._pending.put_nowait(s) for s in self._pending_pre_async]

        # We won't be needing this anymore
        self._pending_pre_async = None

        self._lazy_listen()

    async def shutdown(self, app: web.Application):
        LOGGER.info(f'Closing {self}')
        await scheduler.cancel_task(app, self._task)
        self._loop = None
        self._task = None

    def subscribe(self,
                  exchange_name: str,
                  routing: str,
                  exchange_type: ExchangeType_ = 'topic',
                  on_message: EVENT_CALLBACK_ = None
                  ) -> EventSubscription:
        """Adds a new event subscription to the listener.

        Actual queue declaration to the remote message server is done when connected.
        If the listener is not currently connected, it defers declaration.

        All existing subscriptions are redeclared on the remote if `EventListener`
        loses and recreates the connection.

        Args:
            exchange_name (str):
                Name of the AMQP exchange. Messages are always published to a specific exchange.

            routing (str):
                Filter messages passing through the exchange.
                A routing key is a '.'-separated string, and accepts '#' and '*' wildcards.

            exchange_type (ExchangeType_, optional):
                If the exchange does not yet exist, it will be created with this type.
                Default is `topic`, acceptable values are `topic`, `fanout`, or `direct`.

            on_message (EVENT_CALLBACK_, optional):
                The function to be called when a new message is received.
                If `on_message` is none, it will default to logging the message.

        Returns:
            EventSubscription:
                The newly created subscription.
                This value can safely be discarded: EventListener keeps its own reference.
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

##############################################################################
# Outgoing events
##############################################################################


class EventPublisher(features.ServiceFeature):
    """
    Allows publishing AMQP messages to a central eventbus.

    `EventPublisher` is associated with a single eventbus address,
    but will only create a connection when attempting to publish.

    Connections are re-used for subsequent `publish()` calls.
    """

    def __init__(self,
                 app: web.Application,
                 host: str = None,
                 port: int = None
                 ):
        super().__init__(app)

        self._host: str = host or app['config']['eventbus_host']
        self._port: int = port or app['config']['eventbus_port']
        self._reset()

    @property
    def connected(self):
        return self._transport and self._protocol and self._channel

    def __str__(self):
        return f'<{type(self).__name__} for "{self._host}">'

    def _reset(self):
        self._transport: asyncio.Transport = None
        self._protocol: aioamqp.AmqpProtocol = None
        self._channel: aioamqp.channel.Channel = None

    async def _close(self):
        LOGGER.info(f'Closing {self}')

        try:
            await self._protocol.close()
            self._transport.close()
        except Exception:
            pass
        finally:
            self._reset()

    async def _ensure_channel(self):
        if not self.connected:
            self._transport, self._protocol = await aioamqp.connect(
                host=self._host,
                port=self._port,
                loop=self.app.loop
            )
            self._channel = await self._protocol.channel()

        try:
            await self._protocol.ensure_open()
        except aioamqp.exceptions.AioamqpException:
            await self._close()
            raise

    async def startup(self, *_):
        pass  # Connections are created when attempting to publish

    async def shutdown(self, *_):
        await self._close()

    async def publish(self,
                      exchange: str,
                      routing: str,
                      message: Union[str, dict],
                      exchange_type: ExchangeType_ = 'topic'):
        """
        Publish a new event message.

        Connections are created automatically when calling `publish()`,
        and will attempt to reconnect if connection was lost.

        For more information on publishing AMQP messages,
        see https://www.rabbitmq.com/tutorials/tutorial-three-python.html

        Args:
            exchange (str):
                The AMQP message exchange to publish the message to.
                A new exchange will be created if it does not yet exist.

            routing (str):
                The routing identification with which the message should be published.
                Subscribers use routing information for fine-grained filtering.
                Routing can be expressed as a '.'-separated path.

            message (Union[str, dict]):
                The message body. It will be serialized before transmission.

            exchange_type (ExchangeType_, optional):
                When publishing to a previously undeclared exchange, it will be created.
                `exchange_type` defines how the exchange distributes messages between subscribers.
                The default is 'topic', and acceptable values are: 'topic', 'direct', or 'fanout'.

        Raises:
            aioamqp.exceptions.AioamqpException:
                * Failed to connect to AMQP host
                * Failed to send message
                * `exchange` already exists, but has a different `exchange_type`
        """
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
        warnings.warn(f'Unable to publish {args}: {ex}')
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
