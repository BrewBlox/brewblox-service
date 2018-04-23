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
import errno
import json
import logging
import socket
from concurrent.futures import CancelledError
from typing import Callable, Type, Union

import aio_pika
from aiohttp import web
from brewblox_service.handler import ServiceHandler

import aioamqp

LOGGER = logging.getLogger(__name__)
routes = web.RouteTableDef()

EVENT_CALLBACK_ = Callable[['EventSubscription', str, Union[dict, str]], None]
ExchangeType_ = Type[str]

LISTENER_KEY = 'events.listener'
PUBLISHER_KEY = 'events.publisher'
EVENTBUS_HOST = 'localhost'
EVENTBUS_PORT = 5672


def setup(app: Type[web.Application]):
    app[LISTENER_KEY] = EventListener(app)
    app[PUBLISHER_KEY] = EventPublisher(app)
    app.router.add_routes(routes)


def get_listener(app: Type[web.Application]) -> 'EventListener':
    return app[LISTENER_KEY]


def get_publisher(app: Type[web.Application]) -> 'EventPublisher':
    return app[PUBLISHER_KEY]


async def _default_on_message(queue: Type[aio_pika.Queue], key: str, message: Union[dict, str]):
    LOGGER.info(f'Unhandled event: queue={queue}, key={key} message={message}')


async def _wait_host_resolved(loop: asyncio.BaseEventLoop):  # pragma: no cover
    """
    Dirty patch: use a non-blocking getaddrinfo to wait until host IP can be determined.
    Reference: https://github.com/mosquito/aio-pika/issues/124
    """
    first_attempt = True
    while True:
        try:
            await loop.getaddrinfo(host=EVENTBUS_HOST, port=EVENTBUS_PORT,
                                   family=0, type=socket.SOCK_STREAM, proto=socket.IPPROTO_TCP)
            break
        except OSError as error:
            if error.errno == errno.EINTR:
                # Not actually an error, but still need to try again
                continue

            if first_attempt:
                LOGGER.warn(f'Failed to resolve host "{EVENTBUS_HOST}", will keep trying...')
                first_attempt = False

            await asyncio.sleep(1)
            continue


class EventSubscription():
    def __init__(self,
                 exchange_name: str,
                 routing: str,
                 exchange_type: ExchangeType_=aio_pika.ExchangeType.TOPIC,
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


class EventListener(ServiceHandler):
    def __init__(self, app: web.Application=None):
        super().__init__(app)

        # Asyncio queues need a context loop
        # We'll initialize self._pending when we have one
        self._pending_pre_async = []
        self._pending = None
        self._connection = None
        self._task = None

    def __str__(self):
        return f'<{type(self).__name__} {self._connection}>'

    def _on_connected(self, connection):
        if not connection.is_closed:
            LOGGER.info(f'Connected {self}')
            self._task = connection.loop.create_task(self._listen())

    async def start(self, loop: asyncio.BaseEventLoop):
        # Initialize the async queue now we know which loop we're using
        self._pending = asyncio.Queue(loop=loop)

        # Transfer all subscriptions that were made before the event loop started
        [self._pending.put_nowait(s) for s in self._pending_pre_async]

        # We won't be needing this anymore
        self._pending_pre_async = None

        # TODO(Bob): temporary fix for aio-pika using blocking getaddrinfo
        await _wait_host_resolved(loop)

        # Create the connection
        # We want to start listening it now, and whenever we reconnect
        self._connection = await aio_pika.connect_robust(loop=loop, host=EVENTBUS_HOST)
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
                  exchange_type: ExchangeType_=aio_pika.ExchangeType.TOPIC,
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


class EventPublisher(ServiceHandler):
    def __init__(self, app: web.Application=None, host: str=EVENTBUS_HOST):
        super().__init__(app)

        self._host: str = host
        self._transport = None
        self._protocol: aioamqp.AmqpProtocol = None
        self._channel: aioamqp.channel.Channel = None

    def __str__(self):
        return f'<{type(self).__name__} {self._host}>'

    async def start(self, loop: asyncio.BaseEventLoop):
        self._loop = loop

        self._transport, self._protocol = await aioamqp.connect(
            host=self._host,
            loop=self._loop
        )

    async def close(self):
        LOGGER.info(f'Closing {self}')

        if self._protocol:
            await self._protocol.close()
            self._protocol = None
            self._channel = None

        if self._transport:
            self._transport.close()
            self._protocol = None

    async def publish(self,
                      exchange: str,
                      routing: str,
                      message: Union[str, dict]='',
                      exchange_type: ExchangeType_='topic'):
        assert self._protocol, 'No connection available'
        await self._protocol.ensure_open()

        if not self._channel:
            self._channel = await self._protocol.channel()

        if not self._channel.is_open:
            await self._channel.open()

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
