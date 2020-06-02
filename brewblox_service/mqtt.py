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
from typing import Awaitable, Callable, List, Tuple, Union

import aiomqtt
from aiohttp import web

from brewblox_service import brewblox_logger, features, repeater, strex

LOGGER = brewblox_logger(__name__)
routes = web.RouteTableDef()

ListenerCallback_ = Callable[[str, Union[dict, list]], Awaitable[None]]

RETRY_INTERVAL_S = 5
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

    def __str__(self):
        return f'{self.protocol}://{self.host}:{self.port}{self.path}'


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
        self._disconnect_ev: asyncio.Event = None
        self._subs: List[str] = []
        self._listeners: List[Tuple[str, ListenerCallback_]] = []

    def __str__(self):
        return f'<{type(self).__name__} for {self.config}>'

    @property
    def connected(self) -> bool:
        return self._connect_ev is not None \
            and self._connect_ev.is_set()

    @staticmethod
    def create_client(config: MQTTConfig) -> aiomqtt.Client:
        client = aiomqtt.Client(transport=config.transport,
                                protocol=aiomqtt.MQTTv311)
        client.ws_set_options(path=config.path)

        if config.protocol in ['mqtts', 'wss']:
            client.tls_set(cert_reqs=CERT_NONE)
            client.tls_insecure_set(True)

        return client

    async def startup(self, app: web.Application):
        self._connect_ev = asyncio.Event()
        self._disconnect_ev = asyncio.Event()
        self.client = self.create_client(self.config)
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message
        await super().startup(app)

    async def prepare(self):
        """
        This function is run once, before the run() loop starts.
        Overrides RepeaterFeature.prepare()
        """

    async def run(self):
        """
        This function is repeated until the service exits.
        It blocks until the client raises an error, and then reconnects.
        Overrides RepeaterFeature.run()
        """
        try:
            LOGGER.info(f'Starting {self}')
            await self.client.connect(self.config.host, self.config.port)
            await self.client.loop_forever()

        except asyncio.CancelledError:
            with suppress(Exception):
                # Disconnect and run until the broker acknowledges
                self.client.disconnect()
                done, pending = await asyncio.wait([
                    self.client.loop_forever(),
                    self._disconnect_ev.wait(),
                    asyncio.sleep(2),
                ],
                    return_when=asyncio.FIRST_COMPLETED)
                asyncio.gather(*pending).cancel()
            raise

        except Exception as ex:
            LOGGER.error(f'{self}.run() {strex(ex)}')
            await asyncio.sleep(RETRY_INTERVAL_S)
            raise ex

        finally:
            await self.client.loop_stop()

    def _on_connect(self, client, userdata, flags, rc):
        LOGGER.debug(f'Applying subscribe for {self._subs}')
        for topic in self._subs:
            self.client.subscribe(topic)

        LOGGER.info(f'{self} connected')
        self._disconnect_ev.clear()
        self._connect_ev.set()

    def _on_disconnect(self, client, userdata, rc):
        LOGGER.info(f'{self} disconnected')
        self._connect_ev.clear()
        self._disconnect_ev.set()

    def _on_message(self, client, userdata, message):
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
            asyncio.create_task(cb(topic, json.loads(payload)))

        if not matching:
            LOGGER.info(f'{self} recv topic={topic}, msg={payload[:30]}...')

    async def publish(self, topic: str, message: dict, err=True, **kwargs):
        info = self.client.publish(topic, json.dumps(message), **kwargs)
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
        self._subs.remove(topic)

    async def unlisten(self, topic: str, callback: ListenerCallback_):
        LOGGER.info(f'unlisten({topic})')
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


async def publish(app: web.Application, topic: str, message: dict, **kwargs):
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

    Args:
        app (web.Application):
            The Aiohttp Application object.

        topic (str):
            Must match the `topic` argument earlier used in `subscribe(topic)`.

    Raises:
        ValueError:
            No matching subscription was found
    """
    await handler(app).unsubscribe(topic)


async def unlisten(app: web.Application, topic: str, callback: ListenerCallback_):
    """
    Remove a callback for received event messages.
    Requires setup(app) to have been called first.

    Removes a listener that was set by `listen(topic, callback)`.
    Both `topic` and `callback` must match for the listener to be removed.

    Args:
        app (web.Application):
            The Aiohttp Application object.

        topic (str):
            Must match the `topic` argument earlier used in `listen(topic, callback)`.

        callback (ListenerCallback_):
            Must match the `callback` argument earlier used in `listen(topic, callback)`.

    Raises:
        ValueError:
            No matching listener was found
    """
    await handler(app).unlisten(topic, callback)


@routes.post('/_debug/publish')
async def post_publish(request):
    """
    ---
    tags:
    - MQTT
    summary: Publish event.
    description: Publish a new event message to the event bus.
    operationId: mqtt.publish
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
                topic:
                    type: string
                message:
                    type: object
    """
    args = await request.json()
    await publish(request.app, **args)
    return web.Response()


@routes.post('/_debug/subscribe')
async def post_subscribe(request):
    """
    ---
    tags:
    - MQTT
    summary: Subscribe to events.
    operationId: mqtt.subscribe
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
                topic:
                    type: string
    """
    args = await request.json()
    await subscribe(request.app, args['topic'])
    return web.Response()
