"""
Offers event publishing and subscription for service implementations.

Example use:

    events.setup(app)

    async def on_message(queue, key, message):
        logging.info(f'Message from {queue}: {key} = {message} ({type(message)})')

    listener = events.get_listener(app)
    listener.subscribe('brewblox', 'controller', on_message=on_message)
    listener.subscribe('brewblox', 'controller.*', on_message=on_message)
    listener.subscribe('brewblox', 'controller.#', on_message=on_message)
"""

import asyncio
import json
import logging
from concurrent.futures import CancelledError
from typing import Callable, Type, Union

import aio_pika
from aio_pika import ExchangeType
from aio_pika.queue import ExchangeType_
from aiohttp import web

LOGGER = logging.getLogger(__name__)
routes = web.RouteTableDef()

EVENT_CALLBACK_ = Callable[['EventSubscription', str, Union[dict, str]], None]

LISTENER_KEY = 'events.listener'
PUBLISHER_KEY = 'events.publisher'


def setup(app: Type[web.Application]):
    app[LISTENER_KEY] = EventListener(app)
    app[PUBLISHER_KEY] = EventPublisher(app)
    app.router.add_routes(routes)


def get_listener(app: Type[web.Application]) -> 'EventListener':
    return app[LISTENER_KEY]


def get_publisher(app: Type[web.Application]) -> 'EventPublisher':
    return app[PUBLISHER_KEY]


def _default_on_message(queue: Type[aio_pika.Queue], key: str, message: Union[dict, str]):
    LOGGER.info(f'Unhandled event: queue={queue}, key={key} message={message}')


class EventSubscription():
    def __init__(self,
                 exchange_name: str,
                 routing: str,
                 exchange_type: ExchangeType_=ExchangeType.TOPIC,
                 on_message: EVENT_CALLBACK_=None):
        self._routing = routing
        self._exchange_name = exchange_name
        self._exchange_type = exchange_type
        self._queue = None
        self.on_message = on_message

    def __str__(self):
        return f'<{self._routing} @ {self._exchange_name}>'

    @property
    def on_message(self) -> EVENT_CALLBACK_:
        return self._on_message

    @on_message.setter
    def on_message(self, f: EVENT_CALLBACK_):
        self._on_message = f if f else _default_on_message

    async def declare_on_remote(self, connection: Type[aio_pika.Connection]):
        LOGGER.info(f'Declaring event bus subscription {self} on {connection}')
        channel = await connection.channel()
        exchange = await channel.declare_exchange(self._exchange_name,
                                                  type=self._exchange_type,
                                                  auto_delete=True)
        self._queue = await channel.declare_queue(exclusive=True)
        await self._queue.bind(exchange, self._routing)
        await self._queue.consume(self._relay)

    async def _relay(self, message: Type[aio_pika.IncomingMessage]):
        """Relays incoming messages between the queue and the user callback"""
        message.ack()  # We always acknowledge, regardless of errors in client code
        try:
            await self.on_message(self, message.routing_key, json.loads(message.body))
        except Exception as ex:
            LOGGER.error(f'Exception relaying message in {self}: {ex}')


class EventListener():
    def __init__(self, app: Type[web.Application]=None):
        # Asyncio queues need a context loop
        # We'll initialize self._pending when we have one
        self._pending_pre_async = []
        self._pending = None
        self._connection = None
        self._task = None

        if app:
            self.setup(app)

    def __str__(self):
        return f'<{type(self).__name__} {self._connection}>'

    def setup(self, app):
        app.on_startup.append(self._startup)
        app.on_cleanup.append(self._cleanup)

    async def _startup(self, app: Type[web.Application]):
        await self.start(app.loop)

    async def _cleanup(self, app: Type[web.Application]):
        await self.close()

    def _on_connected(self, connection):
        if not connection.is_closed:
            LOGGER.info(f'Connected {self}')
            self._task = connection.loop.create_task(self._listen())

    async def start(self, loop):
        # Initialize the async queue now we know which loop we're using
        self._pending = asyncio.Queue(loop=loop)

        # Transfer all subscriptions that were made before the event loop started
        [self._pending.put_nowait(s) for s in self._pending_pre_async]

        # We won't be needing this anymore
        self._pending_pre_async = None

        # Create the connection
        # We want to start listening it now, and whenever we reconnect
        self._connection = await aio_pika.connect_robust(loop=loop)
        self._connection.add_reconnect_callback(self._on_connected)
        self._on_connected(self._connection)

    async def close(self):
        LOGGER.info(f'Closing {self}')

        if self._task:
            try:
                self._task.cancel()
                await self._task
            except CancelledError:
                pass

        if self._connection and not self._connection.is_closed:
            await self._connection.close()

    def subscribe(self,
                  exchange_name: str,
                  routing: str,
                  exchange_type: ExchangeType_=ExchangeType.TOPIC,
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

        LOGGER.info(f'New event bus subscription: [{sub}]')
        return sub

    async def _listen(self):
        try:
            while not self._connection.is_closed:
                subscription = await self._pending.get()

                # Check whether connection wasn't closed while waiting for queue
                if not self._connection.is_closed:
                    await subscription.declare_on_remote(self._connection)

                else:  # pragma: no cover
                    # Connection closed while retrieving
                    # Put it back in the queue, we'll declare it after reconnect
                    self._pending.put_nowait(subscription)

        except RuntimeError as ex:  # pragma: no cover
            LOGGER.warn(f'Error in {self} {ex}')
        except CancelledError:
            LOGGER.info(f'Cancelled {self}')


class EventPublisher():
    def __init__(self, app: Type[web.Application]=None):
        self._connection = None
        self._channel = None

        if app:
            self.setup(app)

    def __str__(self):
        return f'<{type(self).__name__} {self._connection}>'

    def setup(self, app):
        app.on_startup.append(self._startup)
        app.on_cleanup.append(self._cleanup)

    async def _startup(self, app: Type[web.Application]):
        await self.start(app.loop)

    async def _cleanup(self, app: Type[web.Application]):
        await self.close()

    async def start(self, loop):
        def _on_connected(connection):
            if not connection.is_closed:
                LOGGER.info(f'Connected {self}')

        self._connection = await aio_pika.connect_robust(loop=loop)
        self._connection.add_reconnect_callback(_on_connected)
        _on_connected(self._connection)

    async def close(self):
        LOGGER.info(f'Closing {self}')
        if self._connection and not self._connection.is_closed:
            await self._connection.close()

    async def publish(self,
                      exchange: str,
                      routing: str,
                      message: Union[str, dict]='',
                      exchange_type: ExchangeType_=ExchangeType.TOPIC):

        # Makes for a more readable error in case of closed connections
        if not self._connection or self._connection.is_closed:
            raise ConnectionRefusedError(
                f'No event bus connection available for {self._connection}')

        # json.dumps() also correctly handles strings
        data = json.dumps(message).encode()

        if not self._channel:
            self._channel = await self._connection.channel()

        exchange = await self._channel.declare_exchange(
            exchange,
            exchange_type,
            auto_delete=True)

        # Push it over the line
        await exchange.publish(
            aio_pika.Message(data),
            routing_key=routing
        )


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

    except ConnectionRefusedError as ex:
        LOGGER.warn(f'Unable to publish {args}: {ex}')
        return web.Response(body='Event bus connection refused', status=500)
