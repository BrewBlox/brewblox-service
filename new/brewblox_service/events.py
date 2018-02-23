"""
Offers event publishing and subscription for service implementations.

Example use:

    events.setup(app)

    async def on_message(queue, key: str, message: str):
        logging.info(f'Message from {queue}: {key} = {message} ({type(message)})')

    listener = events.get_listener(app)
    listener.subscribe('brewblox', 'controller', on_message=on_message)
    listener.subscribe('brewblox', 'controller.*', on_message=on_message)
    listener.subscribe('brewblox', 'controller.#', on_message=on_message)
"""

import json
import logging
from asyncio import Queue, ensure_future
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
    def queue(self) -> Type[aio_pika.Queue]:
        return self._queue

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
        self._queue = await channel.declare_queue(self._routing, exclusive=True)
        await self._queue.bind(exchange, self._routing)
        await self.queue.consume(self._relay)

    async def _relay(self, message: Type[aio_pika.IncomingMessage]):
        """Relays incoming messages between the queue and the user callback"""
        message.ack()  # We always acknowledge, regardless of errors in client code
        try:
            await self.on_message(self, message.routing_key, json.loads(message.body))
        except Exception as ex:
            LOGGER.error(f'Exception relaying message in {self}: {ex}')


class EventListener():
    def __init__(self, app: Type[web.Application]):
        # Asyncio queues need a context loop
        # We'll initialize self._pending on app startup
        self._pending_pre_async = []
        self._pending = None
        self._connection = None
        self._task = None

        # Check whether the app is already running
        # We can either directly schedule our startup, or wait until app startup
        if app.loop:
            ensure_future(self._startup(app), loop=app.loop)
        else:
            app.on_startup.append(self._startup)

        # Always schedule desctruction in app cleanup
        app.on_cleanup.append(self._cleanup)

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

    async def _startup(self, app):
        # Initialize the async queue now we know which loop we're using
        self._pending = Queue(loop=app.loop)

        # Transfer all subscriptions that were made before the event loop started
        [self._pending.put_nowait(s) for s in self._pending_pre_async]

        # We won't be needing this anymore
        self._pending_pre_async = None

        # Create the connection
        # We want to start listening it now, and whenever we reconnect
        self._connection = await aio_pika.connect_robust(loop=app.loop)
        self._connection.add_reconnect_callback(self._schedule)
        self._schedule(self._connection)

    async def _cleanup(self, app):
        """Shutdown hook for the listener.

        Cleans up tasks and resources."""
        LOGGER.info(f'Cleaning up event listener for {self._connection}')

        if self._task:
            self._task.cancel()
            await self._task

        if self._connection and not self._connection.is_closed:
            await self._connection.close()

    def _schedule(self, connection):
        if not connection.is_closed:
            LOGGER.info(f'Event listener connected to {connection}')
            self._task = connection.loop.create_task(self._listen())

    async def _listen(self):
        try:
            while not self._connection.is_closed:
                subscription = await self._pending.get()

                # Check whether connection wasn't closed while waiting for queue
                if not self._connection.is_closed:
                    await subscription.declare_on_remote(self._connection)

                else:
                    # Connection closed while retrieving
                    # We'll have to declare it later
                    # Put it back in the queue
                    self._pending.put_nowait(subscription)

        except RuntimeError as ex:
            LOGGER.warn(f'Event listener error: {ex}. Connection = {self._connection}')
        except CancelledError:
            LOGGER.info(f'Event listener cancelled for {self._connection}')


class EventPublisher():
    def __init__(self, app: Type[web.Application]):
        self._connection = None
        self._channel = None

        # Check whether the app is already running
        # We can either directly schedule our startup, or wait until app startup
        if app.loop:
            ensure_future(self._startup(app), loop=app.loop)
        else:
            app.on_startup.append(self._startup)

        # Always schedule desctruction in app cleanup
        app.on_cleanup.append(self._cleanup)

    async def _startup(self, app):
        def _on_connected(connection):
            if not connection.is_closed:
                LOGGER.info(f'Event publisher connected to {connection}')

        self._connection = await aio_pika.connect_robust(loop=app.loop)
        self._connection.add_reconnect_callback(_on_connected)
        _on_connected(self._connection)

    async def _cleanup(self, app):
        LOGGER.info(f'Cleaning up event publisher for {self._connection}')
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


@routes.post('/publish')
async def post_publish(request):
    """
    ---
    tags:
    - Events
    summary: Publish event.
    description: Publish a new event message to the event bus.
    operationId: events.publish
    produces: text/plain
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
