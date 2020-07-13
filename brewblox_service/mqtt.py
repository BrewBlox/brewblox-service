"""
Offers publishing and subscribing to MQTT events.

Example use:

    from brewblox_service import mqtt, scheduler

    scheduler.setup(app)
    mqtt.setup(app)

    async def on_message(topic, body):
        print(f'Message published to {topic}')
        print(f'Message content: {body}')

    mqtt.listen(app, 'brewcast/state/a', on_message)
    mqtt.listen(app, 'brewcast/state/b', on_message)

    mqtt.subscribe(app, 'brewcast/state/#')

    await mqtt.publish('app', 'brewcast/state', {'example': True})
    await mqtt.publish('app', 'brewcast/state/a', {'example': True})
"""

import asyncio
import json
from contextlib import suppress
from dataclasses import dataclass, field
from ssl import CERT_NONE
from typing import Awaitable, Callable, List, Optional, Tuple, Union

import aiomqtt
from aiohttp import web
from aiohttp_apispec import docs, request_schema
from marshmallow import Schema, fields

from brewblox_service import brewblox_logger, features, strex

LOGGER = brewblox_logger(__name__)
routes = web.RouteTableDef()

EventData_ = Optional[Union[dict, list]]
ListenerCallback_ = Callable[[str, EventData_], Awaitable[None]]

DEFAULT_PORTS = {
    'mqtt': 1883,
    'mqtts': 8883,
    'ws': 80,
    'wss': 443,
}


def decoded(msg: Union[str, bytes, bytearray]):
    if isinstance(msg, (bytes, bytearray)):
        return msg.decode()
    return msg


@dataclass
class MQTTConfig:
    protocol: str
    host: str
    port: int
    path: str
    transport: str = field(init=False)
    client_will: dict = field(init=False)

    def __post_init__(self):
        if self.protocol not in ['ws', 'wss', 'mqtt', 'mqtts']:
            raise ValueError(f'Invalid protocol: {self.protocol}')

        if self.protocol.startswith('ws'):
            self.transport = 'websockets'
            self.path = self.path or ''
        else:
            self.transport = 'tcp'
            self.path = ''

        if not self.port or self.port == 5672:
            self.port = DEFAULT_PORTS[self.protocol]

        self.client_will = {}

    def __str__(self):
        return f'{self.protocol}://{self.host}:{self.port}{self.path}'


class EventHandler(features.ServiceFeature):
    """
    Connection handler class for MQTT events.
    Handles both TCP and Websocket connections.

    Automatically reconnects and resubscribes when connection is lost.

    Subscribe and listen are handled separately.
    You can subscribe to a wildcard topic, and then set callbacks for specific topics.

    Options are supplied either kwargs, or the service config.

    Kwargs:
        protocol ('ws' | 'wss' | 'mqtt' | 'mqtts'):
            Transport protocol used:
            - ws: websockets
            - wss: websockets over HTTPS
            - mqtt: TCP
            - mqtts: TCP + TLS/SSL

        host (str):
            Hostname of the broker.
            The default hostname of the RabbitMQ broker is 'eventbus'.
            This is accessible only from inside a Brewblox network.
            Outside of a Brewblox network, it is the hostname of the Traefik gateway.

        port (int):
            Port used by the broker.
            The default ports are:
            - ws: 80
            - wss': 443
            - mqtt': 1883
            - mqtts: 8883

            Note that this assumes ws/wss are connected to the Traefik gateway.
            If you are using websockets, and are directly connected to RabbitMQ, values are:
            - ws: 15675
            - wss: 15673

        path (str):
            Path to the broker.
            This value is ignored if mqtt/mqtts protocols are set.
            The default path for the RabbitMQ broker is '/eventbus'

            Examples: (formatted as <protocol>://<host>:<port><path>)
                ws://eventbus:15675/eventbus
                wss://BREWBLOX_HOST:443/eventbus
    """

    def __init__(self, app: web.Application, **args):
        super().__init__(app)

        config = app['config']
        protocol = args.get('protocol', config['mqtt_protocol'])
        host = args.get('host', config['mqtt_host'])
        port = args.get('port', config['mqtt_port'])
        path = args.get('path', config['mqtt_path'])
        self.config = MQTTConfig(protocol, host, port, path)
        self.client: aiomqtt.Client = None

        self._connect_ev: asyncio.Event = None
        self._subs: List[str] = []
        self._listeners: List[Tuple[str, ListenerCallback_]] = []

    def __str__(self):
        return f'<{type(self).__name__} for {self.config}>'

    @property
    def connected(self) -> bool:
        return self.client is not None \
            and self._connect_ev is not None \
            and self._connect_ev.is_set()

    def set_client_will(self, topic: str, message: EventData_, **kwargs):
        if self.client:
            raise RuntimeError('Client will must be set before startup')
        payload = json.dumps(message) if message is not None else None
        self.config.client_will = dict(topic=topic,
                                       payload=payload,
                                       **kwargs)

    @staticmethod
    def create_client(config: MQTTConfig) -> aiomqtt.Client:
        client = aiomqtt.Client(transport=config.transport,
                                protocol=aiomqtt.MQTTv311)
        client.ws_set_options(path=config.path)

        if config.protocol in ['mqtts', 'wss']:
            client.tls_set(cert_reqs=CERT_NONE)
            client.tls_insecure_set(True)

        if config.client_will:
            client.will_set(**config.client_will)

        return client

    async def startup(self, app: web.Application):
        self._connect_ev = asyncio.Event()
        self.client = self.create_client(self.config)
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message

        LOGGER.info(f'Starting {self}')
        self.client.connect_async(self.config.host, self.config.port)
        self.client.loop_start()

    async def shutdown(self, app: web.Application):
        if self.client:
            self.client.disconnect()
            await self.client.loop_stop()
            self.client = None

    def _on_connect(self, *args):
        LOGGER.debug(f'Applying subscribe for {self._subs}')
        for topic in self._subs:
            self.client.subscribe(topic)

        LOGGER.info(f'{self} connected')
        self._connect_ev.set()

    def _on_disconnect(self, *args):
        LOGGER.info(f'{self} disconnected')
        self._connect_ev.clear()

    async def _handle_callback(self, cb, topic, payload):
        try:
            await cb(topic, json.loads(payload) if payload else None)
        except Exception as ex:
            LOGGER.error(f'Exception handling MQTT callback for {topic}: {strex(ex)}')

    def _on_message(self, client, userdata, message, *args):
        try:
            topic = decoded(message.topic)
            payload = decoded(message.payload)
        except UnicodeDecodeError:  # pragma: no cover
            LOGGER.error('Skipping malformed MQTT event')
            return

        matching = [cb
                    for (sub, cb) in self._listeners
                    if aiomqtt.topic_matches_sub(sub, topic)]

        for cb in matching:
            asyncio.create_task(self._handle_callback(cb, topic, payload))

        if not matching:
            LOGGER.info(f'{self} recv topic={topic}, msg={payload[:30]}...')

    async def publish(self, topic: str, message: EventData_, err=True, **kwargs):
        payload = json.dumps(message) if message is not None else None
        info = self.client.publish(topic, payload, **kwargs)
        error = aiomqtt.error_string(info.rc)
        LOGGER.debug(f'publish({topic}) -> {error}')
        if info.rc != 0 and err:
            raise ConnectionError(f'Publish error="{error}", topic="{topic}"')

    async def subscribe(self, topic: str):
        LOGGER.info(f'subscribe({topic})')
        self._subs.append(topic)
        if self.connected:
            self.client.subscribe(topic)

    async def listen(self, topic: str, callback: ListenerCallback_):
        LOGGER.info(f'listen({topic})')
        self._listeners.append((topic, callback))

    async def unsubscribe(self, topic: str):
        LOGGER.info(f'unsubscribe({topic})')
        if self.connected:
            self.client.unsubscribe(topic)
        with suppress(ValueError):
            self._subs.remove(topic)

    async def unlisten(self, topic: str, callback: ListenerCallback_):
        LOGGER.info(f'unlisten({topic})')
        with suppress(ValueError):
            self._listeners.remove((topic, callback))


def setup(app: web.Application):
    """
    Initializes the EventHandler in the app context.

    Args:
        app (web.Application):
            The Aiohttp Application object.
    """
    features.add(app, EventHandler(app))
    app.router.add_routes(routes)


def handler(app: web.Application) -> EventHandler:
    """
    Get registered EventHandler.
    Requires setup(app) to have been called first.

    Args:
        app (web.Application):
            The Aiohttp Application object.
    """
    return features.get(app, EventHandler)


def set_client_will(app: web.Application,
                    topic: str,
                    message: EventData_ = None,
                    **kwargs):
    """
    Set MQTT Last Will and Testament for client.
    Requires setup(app) to have been called first.
    Must be called before startup.

    Args:
        app (web.Application):
            The Aiohttp Application object.

        topic (str):
            The MQTT message topic. Cannot include wildcards.

        message (dict, None):
            A JSON-serializable object, or None.
    """
    handler(app).set_client_will(topic, message, **kwargs)


async def publish(app: web.Application,
                  topic: str,
                  message: EventData_,
                  **kwargs):
    """
    Publish a new event message.

    Shortcut for `handler(app).subscribe(topic, message)`.
    Requires setup(app) to have been called first.

    Args:
        app (web.Application):
            The Aiohttp Application object.

        topic (str):
            The MQTT message topic. Cannot include wildcards.

        message (dict):
            A JSON-serializable object.
    """
    await handler(app).publish(topic, message, **kwargs)


async def subscribe(app: web.Application, topic: str):
    """
    Subscribe to event messages.
    Requires setup(app) to have been called first.

    In order to get callbacks for events, listen() must also be used.
    You can register multiple listeners for a single subscribed topic.

    See: http://www.steves-internet-guide.com/understanding-mqtt-topics/

    Args:
        app (web.Application):
            The Aiohttp Application object.

        topic (str):
            A filter for message topics.
            Can include the '+' and '#' wildcards.
    """
    await handler(app).subscribe(topic)


async def listen(app: web.Application, topic: str, callback: ListenerCallback_):
    """
    Set a listener for event messages.
    Requires setup(app) to have been called first.

    In order to get callbacks, subscribe() must also be used.
    You can register multiple listeners for a single subscribed topic.

    See: http://www.steves-internet-guide.com/understanding-mqtt-topics/

    Args:
        app (web.Application):
            The Aiohttp Application object.

        topic (str):
            A filter for message topics.
            Can include the '+' and '#' wildcards.

    """
    await handler(app).listen(topic, callback)


async def unsubscribe(app: web.Application, topic: str):
    """
    Unsubscribe to event messages.
    Requires setup(app) to have been called first.

    Removes a subscription that was set by `subscribe(topic)`.
    Does nothing if no subscription can be found.

    Args:
        app (web.Application):
            The Aiohttp Application object.

        topic (str):
            Must match the `topic` argument earlier used in `subscribe(topic)`.
    """
    await handler(app).unsubscribe(topic)


async def unlisten(app: web.Application, topic: str, callback: ListenerCallback_):
    """
    Remove a callback for received event messages.
    Requires setup(app) to have been called first.

    Removes a listener that was set by `listen(topic, callback)`.
    Both `topic` and `callback` must match for the listener to be removed.
    Does nothing if no listener can be found found.

    Args:
        app (web.Application):
            The Aiohttp Application object.

        topic (str):
            Must match the `topic` argument earlier used in `listen(topic, callback)`.

        callback (ListenerCallback_):
            Must match the `callback` argument earlier used in `listen(topic, callback)`.
    """
    await handler(app).unlisten(topic, callback)


class MQTTPublishSchema(Schema):
    topic = fields.String()
    message = fields.Dict()


class MQTTSubscribeSchema(Schema):
    topic = fields.String()


@docs(
    tags=['MQTT'],
    summary='Publish an event message.',
    description='This is a debugging / diagnostics endpoint.'
)
@routes.post('/_debug/publish')
@request_schema(MQTTPublishSchema())
async def post_publish(request):
    data = request['data']
    await publish(request.app, data['topic'], data['message'])
    return web.Response()


@docs(
    tags=['MQTT'],
    summary='Subscribe to event messages.',
    description='This is a debugging / diagnostics endpoint. '
    'Messages received for this subscription will be logged and then discarded.'
)
@routes.post('/_debug/subscribe')
@request_schema(MQTTSubscribeSchema())
async def post_subscribe(request):
    await subscribe(request.app, request['data']['topic'])
    return web.Response()
