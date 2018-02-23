"""
Offers event publishing and subscription for service implementations.
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

EVENT_CALLBACK_ = Callable[['EventSubscription', Union[dict, str]], None]

LISTENER_KEY = 'events.listener'
PUBLISHER_KEY = 'events.publisher'
LOOP_SLEEP_S = 0.01


def _default_on_message(queue: Type[aio_pika.Queue], message: Union[dict, str]):
    LOGGER.info(f'Unhandled event received on [{queue}]: {message}')


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

    async def declare(self, connection: Type[aio_pika.Connection]):
        LOGGER.info(f'Declaring eventbus subscription {self}')
        channel = await connection.channel()
        exchange = await channel.declare_exchange(self._exchange_name,
                                                  type=self._exchange_type,
                                                  auto_delete=True)
        self._queue = await channel.declare_queue(self._routing, exclusive=True)
        await self._queue.bind(exchange, self._routing)
        await self.queue.consume(self._relay)

    async def _relay(self, message: Type[aio_pika.Message]):
        message.ack()
        try:
            await self.on_message(self, json.loads(message.body))
        except Exception as ex:
            LOGGER.exception(ex)


class EventListener():
    def __init__(self, app: Type[web.Application]):
        # Asyncio queues need a context loop
        # We'll defer initializing _deferred
        self._sync_deferred = []
        self._deferred = None
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

        on_message(queue, Union[dict, str]) can be specified. It will attempt to convert a message to json.
        Failing that, it is called with a string.

        If on_message() is not set, it will default to logging the message.
        """
        sub = EventSubscription(
            exchange_name,
            routing,
            exchange_type,
            on_message=on_message
        )

        if self._deferred is not None:
            self._deferred.put_nowait(sub)
        else:
            self._sync_deferred.append(sub)

        LOGGER.info(f'New eventbus subscription: [{sub}]')
        return sub

    async def _startup(self, app):
        # Transfer all subscriptions that were made before the event loop started
        self._deferred = Queue(loop=app.loop)
        [self._deferred.put_nowait(s) for s in self._sync_deferred]
        self._sync_deferred = None

        self._connection = await aio_pika.connect_robust(loop=app.loop)
        self._connection.add_reconnect_callback(self._schedule)
        self._schedule(self._connection)

    async def _cleanup(self, app):
        if self._task:
            self._task.cancel()
            await self._task

    def _schedule(self, connection):
        if not connection.is_closed:
            LOGGER.info('Starting event listener')
            self._task = connection.loop.create_task(self._listen())

    async def _listen(self):
        try:
            while not self._connection.is_closed:
                undeclared = await self._deferred.get()
                if not self._connection.is_closed:
                    await undeclared.declare(self._connection)
                else:
                    # Connection closed while retrieving
                    # We'll have to declare it later
                    self._deferred.put_nowait(undeclared)
        except RuntimeError as ex:
            LOGGER.warn(f'Event listener ran into an error: {ex}')
        except CancelledError:
            if self._connection and not self._connection.is_closed:
                await self._connection.close()


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
        self._connection = await aio_pika.connect_robust(loop=app.loop)
        self._channel = await self._connection.channel()

    async def _cleanup(self, app):
        if self._connection and not self._connection.is_closed:
            await self._connection.close()

    async def publish(self,
                      exchange: str,
                      routing: str,
                      message: Union[str, dict]='',
                      exchange_type: ExchangeType_=ExchangeType.TOPIC):

        # Makes for a more readable error in case of closed connections
        if not self._connection or self._connection.is_closed:
            raise ConnectionRefusedError('No event bus connection available')

        # json.dumps() also correctly handles strings
        data = json.dumps(message).encode()

        exchange = await self._channel.declare_exchange(
            exchange,
            exchange_type,
            auto_delete=True)

        # Push it over the line
        await exchange.publish(
            aio_pika.Message(data),
            routing_key=routing
        )


def setup(app: Type[web.Application]):
    app[LISTENER_KEY] = EventListener(app)
    app[PUBLISHER_KEY] = EventPublisher(app)
    app.router.add_routes(routes)


def get_listener(app: Type[web.Application]) -> Type[EventListener]:
    return app[LISTENER_KEY]


def get_publisher(app: Type[web.Application]) -> Type[EventPublisher]:
    return app[PUBLISHER_KEY]


@routes.post('/subscribe')
async def post_subscribe(request):
    args = await request.json()
    get_listener(request.app).subscribe(
        'brewblox',
        args['routing']
    )
    return web.Response()


@routes.post('/publish')
async def post_publish(request):
    args = await request.json()
    await get_publisher(request.app).publish(
        'brewblox',
        args['routing'],
        args['message']
    )
    return web.Response()
