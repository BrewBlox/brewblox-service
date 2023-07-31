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
    client_will: Optional[Will] = None
    transport: str = field(init=False)
    tls_params: Optional[TLSParameters] = field(init=False)

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

        if self.protocol in ['mqtts', 'wss']:
            self.tls_params = TLSParameters(cert_reqs=CERT_NONE)
        else:
            self.tls_params = None

    def __str__(self):
        return f'{self.protocol}://{self.host}:{self.port}{self.path}'

    def make_client(self) -> Client:
        client = Client(hostname=self.host,
                        port=self.port,
                        transport=self.transport,
                        websocket_path=self.path,
                        tls_params=self.tls_params,
                        will=self.client_will,
                        logger=MQTT_LOGGER)

        if self.tls_params:
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
                 protocol: Optional[models.MqttProtocol] = None,
                 host: Optional[str] = None,
                 port: Optional[int] = None,
                 path: Optional[str] = None,
                 client_will: Optional[Will] = None,
                 publish_will_before_shutdown: bool = True,
                 **kwargs):
        super().__init__(app, **kwargs)

        config: models.BaseServiceConfig = app['config']
        self.config = MQTTConfig(protocol or config.mqtt_protocol,
                                 host or config.mqtt_host,
                                 port or config.mqtt_port,
                                 path or config.mqtt_path,
                                 client_will)
        self.client: Client = self.config.make_client()

        self._ready_ev = asyncio.Event()
        self._connect_delay: int = 0
        self._subscribed_topics: list[str] = []
        self._listeners: list[tuple[str, ListenerCallback_]] = []
        self._publish_will_before_shutdown = publish_will_before_shutdown

    def __str__(self):
        return f'<{type(self).__name__} for {self.config}>'

    @property
    def ready(self) -> asyncio.Event:
        return self._ready_ev

    async def _handle_callback(self, cb: ListenerCallback_, message: Message):
        try:
            await cb(str(message.topic), decoded(message.payload))
        except Exception as ex:
            LOGGER.error(f'Exception handling MQTT callback for {message.topic}: {strex(ex)}')

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
                                    if message.topic.matches(topic)
                                    # Workaround for a bug: https://github.com/sbtinstruments/aiomqtt/issues/239
                                    # TODO(Bob) remove when fixed
                                    or (topic.endswith('/#') and message.topic.matches(topic[:-2]))]

                        for cb in matching:
                            asyncio.create_task(self._handle_callback(cb, message))

                        if not matching:
                            LOGGER.debug(f'{self} recv {message}')

        finally:
            self._ready_ev.clear()

    async def before_shutdown(self, app: web.Application):
        if self._publish_will_before_shutdown:
            with suppress(Exception):
                await self.client.publish(**vars(self.config.client_will))

    async def publish(self,
                      topic: str,
                      payload: PayloadType,
                      qos=0,
                      retain=False,
                      err=True,
                      **kwargs):
        try:
            await self.client.publish(topic,
                                      payload,
                                      qos=qos,
                                      retain=retain,
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


def setup(app: web.Application,
          protocol: Optional[models.MqttProtocol] = None,
          host: Optional[str] = None,
          port: Optional[int] = None,
          path: Optional[str] = None,
          client_will: Optional[Will] = None,
          publish_will_before_shutdown: bool = True,
          **kwargs):
    """
    Initializes the EventHandler in the app context.

    Args:
        app (web.Application):
            The Aiohttp Application object.

        protocol (models.MqttProtocol, optional):
            Override the connection protocol.
            If not set, app['config']['mqtt_protocol'] is used.

        host (str, optional):
            Override the broker host.
            If not set, app['config']['mqtt_host'] is used.

        port (int, optional):
            Override the broker port.
            If not set, app['config']['mqtt_port'] is used.

        path (str, optional):
            Override the broker path for WS connections.
            If not set, app['config']['mqtt_path'] is used.

        client_will (Will, optional):
            Set Last Will and Testament for the MQTT connection.

        publish_will_before_shutdown (bool, optional):
            If set, the handler will attempt to send `client_will`
            before a normal shutdown.

    """
    features.add(app,
                 EventHandler(app,
                              protocol=protocol,
                              host=host,
                              port=port,
                              path=path,
                              client_will=client_will,
                              publish_will_before_shutdown=publish_will_before_shutdown,
                              **kwargs))


def fget(app: web.Application) -> EventHandler:
    """
    Get registered EventHandler.
    Requires setup(app) to have been called first.

    Args:
        app (web.Application):
            The Aiohttp Application object.
    """
    return features.get(app, EventHandler)


async def publish(app: web.Application,
                  topic: str,
                  payload: PayloadType,
                  qos=0,
                  retain=False,
                  err=True,
                  **kwargs):
    """
    Publish a new event message.

    Shortcut for `fget(app).subscribe(topic, message)`.
    Requires setup(app) to have been called first.

    Args:
        app (web.Application):
            The Aiohttp Application object.

        topic (str):
            The MQTT message topic. Cannot include wildcards.

        payload (str, bytes, None):
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
    await fget(app).publish(topic=topic,
                            payload=payload,
                            qos=qos,
                            retain=retain,
                            err=err,
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
    await fget(app).subscribe(topic)


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
    await fget(app).listen(topic, callback)


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
    await fget(app).unsubscribe(topic)


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
    await fget(app).unlisten(topic, callback)
