"""
Offers publishing and subscribing to MQTT events.

Example use:

    import json
    from brewblox_service import mqtt, scheduler

    scheduler.setup(app)
    mqtt.setup(app)

    async def on_message(topic, body):
        print(f'Message topic: {topic}')
        print(f'Message content: {body}')

    mqtt.listen(app, 'brewcast/state/a', on_message)
    mqtt.listen(app, 'brewcast/state/b', on_message)

    mqtt.subscribe(app, 'brewcast/state/#')

    await mqtt.publish('app', 'brewcast/state', json.dumps({'example': True}))
    await mqtt.publish('app', 'brewcast/state/a', json.dumps({'example': True}))
"""

import asyncio
from contextlib import suppress
from dataclasses import dataclass, field
from ssl import CERT_NONE
from typing import Awaitable, Callable, Optional

from aiohttp import web
from aiomqtt import Client, Message, MqttError, TLSParameters, Will
from aiomqtt.types import PayloadType

from brewblox_service import brewblox_logger, features, models, repeater, strex

LOGGER = brewblox_logger(__name__)
MQTT_LOGGER = brewblox_logger('aiomqtt')

ListenerCallback_ = Callable[[str, str], Awaitable[None]]

RECONNECT_INTERVAL_S = 2
INTERACTION_TIMEOUT_S = 5
DEFAULT_PORTS = {
    'mqtt': 1883,
    'mqtts': 8883,
    'ws': 80,
    'wss': 443,
}


def decoded(msg: PayloadType):
    if isinstance(msg, (bytes, bytearray)):
        return msg.decode()
    return msg


@dataclass
class MQTTConfig:
    protocol: str
    host: str
    port: int
    path: str
    client_will: Optional[dict] = None
    transport: str = field(init=False)

    def __post_init__(self):
        if self.protocol not in ['ws', 'wss', 'mqtt', 'mqtts']:
            raise ValueError(f'Invalid protocol: {self.protocol}')

        if self.protocol.startswith('ws'):
            self.transport = 'websockets'
            self.path = self.path or ''
        else:
            self.transport = 'tcp'
            self.path = ''

        if not self.port:
            self.port = DEFAULT_PORTS[self.protocol]

    def __str__(self):
        return f'{self.protocol}://{self.host}:{self.port}{self.path}'


def _make_client(config: MQTTConfig) -> Client:
    secure_protocol = config.protocol in ['mqtts', 'wss']
    tls_params = None
    will = None

    if secure_protocol:
        tls_params = TLSParameters(cert_reqs=CERT_NONE)

    if config.client_will:
        will = Will(**config.client_will)

    client = Client(hostname=config.host,
                    port=config.port,
                    transport=config.transport,
                    websocket_path=config.path,
                    tls_params=tls_params,
                    will=will,
                    logger=MQTT_LOGGER)

    if secure_protocol:
        client._client.tls_insecure_set(True)

    return client


class EventHandler(repeater.RepeaterFeature):
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
            The default path for the broker is '/eventbus'

            Examples: (formatted as <protocol>://<host>:<port><path>)
                ws://eventbus:15675/eventbus
                wss://BREWBLOX_HOST:443/eventbus
    """

    def __init__(self,
                 app: web.Application,
                 protocol: models.MqttProtocol = None,
                 host: str = None,
                 port: int = None,
                 path: str = None,
                 **kwargs):
        super().__init__(app, **kwargs)

        config: models.ServiceConfig = app['config']
        protocol = protocol or config.mqtt_protocol
        host = host or config.mqtt_host
        port = port or config.mqtt_port
        path = path or config.mqtt_path
        self.config = MQTTConfig(protocol, host, port, path)
        self.client: Client = None

        self._ready_ev = asyncio.Event()
        self._connect_delay: int = 0
        self._subscribed_topics: list[str] = []
        self._listeners: list[tuple[str, ListenerCallback_]] = []

    def __str__(self):
        return f'<{type(self).__name__} for {self.config}>'

    @property
    def ready(self) -> asyncio.Event:
        return self._ready_ev

    def set_client_will(self, topic: str, message: PayloadType, **kwargs):
        if self.client:
            raise RuntimeError('Client will must be set before startup')
        self.config.client_will = dict(topic=topic,
                                       payload=message,
                                       **kwargs)

    async def _handle_callback(self, cb: ListenerCallback_, message: Message):
        try:
            await cb(str(message.topic), decoded(message.payload))
        except Exception as ex:
            LOGGER.error(f'Exception handling MQTT callback for {message.topic}: {strex(ex)}')

    async def startup(self, app: web.Application):
        self.client = _make_client(self.config)

    async def run(self):
        await asyncio.sleep(self._connect_delay)
        self._connect_delay = RECONNECT_INTERVAL_S

        try:
            async with self.client:
                async with self.client.messages() as messages:
                    if self._subscribed_topics:
                        await self.client.subscribe([(t, 0) for t in self._subscribed_topics],
                                                    timeout=INTERACTION_TIMEOUT_S)

                    LOGGER.debug(f'{self} is ready')
                    self._ready_ev.set()

                    async for message in messages:  # pragma: no cover
                        matching = [cb
                                    for (topic, cb) in self._listeners
                                    if message.topic.matches(topic)]

                        for cb in matching:
                            asyncio.create_task(self._handle_callback(cb, message))

                        if not matching:
                            LOGGER.debug(f'{self} recv {message}')

        finally:
            self._ready_ev.clear()

    async def publish(self,
                      topic: str,
                      message: PayloadType,
                      retain=False,
                      qos=0,
                      err=True,
                      **kwargs):
        try:
            await self.client.publish(topic,
                                      message,
                                      retain=retain,
                                      qos=qos,
                                      timeout=INTERACTION_TIMEOUT_S,
                                      **kwargs)
            LOGGER.debug(f'publish({topic}) -> OK')
        except MqttError as ex:
            LOGGER.debug(f'publish({topic}) -> {strex(ex)}')
            if err:
                raise ConnectionError(f'Publish error="{strex(ex)}", topic="{topic}"') from ex

    async def subscribe(self, topic: str):
        LOGGER.debug(f'subscribe({topic})')
        self._subscribed_topics.append(topic)
        with suppress(MqttError):
            await self.client.subscribe(topic, timeout=INTERACTION_TIMEOUT_S)

    async def listen(self, topic: str, callback: ListenerCallback_):
        LOGGER.debug(f'listen({topic})')
        self._listeners.append((topic, callback))

    async def unsubscribe(self, topic: str):
        LOGGER.debug(f'unsubscribe({topic})')
        with suppress(MqttError):
            await self.client.unsubscribe(topic, timeout=INTERACTION_TIMEOUT_S)
        with suppress(ValueError):
            self._subscribed_topics.remove(topic)

    async def unlisten(self, topic: str, callback: ListenerCallback_):
        LOGGER.debug(f'unlisten({topic})')
        with suppress(ValueError):
            self._listeners.remove((topic, callback))


def setup(app: web.Application, **kwargs):
    """
    Initializes the EventHandler in the app context.

    Args:
        app (web.Application):
            The Aiohttp Application object.
    """
    features.add(app, EventHandler(app, **kwargs))


def fget(app: web.Application) -> EventHandler:
    """
    Get registered EventHandler.
    Requires setup(app) to have been called first.

    Args:
        app (web.Application):
            The Aiohttp Application object.
    """
    return features.get(app, EventHandler)


def handler(app: web.Application) -> EventHandler:  # pragma: no cover
    """
    Deprecated: use fget() instead

    Get registered EventHandler.
    Requires setup(app) to have been called first.

    Args:
        app (web.Application):
            The Aiohttp Application object.
    """
    return features.get(app, EventHandler)


def set_client_will(app: web.Application,
                    topic: str,
                    message: PayloadType = None,
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

        message (str, bytes, None):
            The payload that will be published by the broker on our behalf after disconnecting.
    """
    handler(app).set_client_will(topic, message, **kwargs)


async def publish(app: web.Application,
                  topic: str,
                  message: PayloadType,
                  retain=False,
                  qos=0,
                  err=True,
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

        message (str, bytes, None):
            The message payload.

        retain (bool):
            The MQTT retain flag.
            When a new listener subscribes to a topic,
            it is sent the last retained message by the broker.

        qos (int):
            The MQTT quality-of-service flag.
            Must be 0, 1, or 2.

        err (bool):
            Local flag to determine error handling.
            If set to `False`, no exception is raised when the message could not be published.
    """
    await handler(app).publish(topic,
                               message,
                               retain,
                               qos,
                               err,
                               **kwargs)


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

        callback (Callable[[str, str], Awaitable[None]]):
            The callback that will be invoked if a message is received.
            It is expected to be an async function that takes two arguments: topic and payload.

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

        callback (Callable[[str, str], Awaitable[None]]):
            Must match the `callback` argument earlier used in `listen(topic, callback)`.
    """
    await handler(app).unlisten(topic, callback)
