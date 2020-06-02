"""
DEPRECATED: USE THE MQTT MODULE INSTEAD.

Offers event publishing and subscription for service implementations.

Example use:

    from brewblox_service import scheduler, events

    scheduler.setup(app)
    events.setup(app)

    async def on_message(subscription, key, message):
        print(f'Message from {subscription}: {key} = {message} ({type(message)})')

    events.subscribe(app, 'brewblox', 'controller', on_message=on_message)
    events.subscribe(app, 'brewblox', 'controller.*', on_message=on_message)
    events.subscribe(app, 'brewblox', 'controller.#', on_message=on_message)

    await events.publish(app, 'brewblox', 'controller.value', {'example': True})

"""
import asyncio
import json
import logging
import queue
import warnings
from datetime import timedelta
from typing import Callable, Coroutine, List, Optional, Union

import aioamqp
from aiohttp import web
from deprecated import deprecated

from brewblox_service import brewblox_logger, features, repeater, strex

LOGGER = brewblox_logger(__name__)
routes = web.RouteTableDef()

EvtCallbackType_ = Callable[['EventSubscription', str, Union[dict, str]], Coroutine]
ExchangeType_ = str  # Literal['topic', 'fanout', 'direct']

RECONNECT_INTERVAL = timedelta(seconds=1)
PENDING_WAIT_TIMEOUT = timedelta(seconds=5)

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
                 on_message: Optional[EvtCallbackType_] = None):
        self._routing: str = routing
        self._exchange_name: str = exchange_name
        self._exchange_type: ExchangeType_ = exchange_type
        self._on_message: EvtCallbackType_ = on_message or _default_on_message

    def __str__(self):
        return f'<{self._routing} @ {self._exchange_name}>'

    @property
    def on_message(self) -> EvtCallbackType_:
        return self._on_message

    @on_message.setter
    def on_message(self, f: Optional[EvtCallbackType_]):
        self._on_message = f or _default_on_message

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


class EventListener(repeater.RepeaterFeature):
    """
    Allows subscribing to AMQP messages published to a central event bus.

    `EventListener` will maintain a persistent connection to the AMQP host,
    and ensures that all subscriptions remain valid if the connection is lost and reestablished.
    """

    def __init__(self,
                 app: web.Application,
                 host: str = None,
                 port: int = None,
                 ):
        super().__init__(app)

        self._host: str = host or app['config']['eventbus_host']
        self._port: int = port or app['config']['eventbus_port']
        self._last_ok: bool = True

        # Asyncio queues need a context loop
        # We'll replace _pending with an asyncio.Queue when we can
        self._pending: Union[queue.Queue, asyncio.Queue] = queue.Queue()
        self._active: List[EventSubscription] = []

        # Same as the Queue: it will be initialized when async
        # The background task will await this before connecting
        self._has_pending: Optional[asyncio.Event] = None

    def __str__(self):
        return f'<{type(self).__name__} for {self._host}>'

    async def prepare(self):
        """
        Overrides RepeaterFeature.prepare().
        This function will be called once before the run() loop.
        """
        # Initialize async versions of objects
        # Don't discard the sync queue
        sync_pending = self._pending
        self._pending = asyncio.Queue()
        self._has_pending = asyncio.Event()

        # Migrate data from sync Queue to async Queue
        while sync_pending.qsize() > 0:
            self._pending.put_nowait(sync_pending.get_nowait())
            self._has_pending.set()

        await self._has_pending.wait()
        LOGGER.info(f'{self} now listening')

    async def run(self):
        """
        Overrides RepeaterFeature.run().
        This function will be called in a loop in a background Task.
        """
        transport: asyncio.Transport = None
        protocol: aioamqp.AmqpProtocol = None
        channel: aioamqp.channel.Channel = None

        try:
            transport, protocol = await aioamqp.connect(
                host=self._host,
                port=self._port,
                login_method='PLAIN',
            )
            channel = await protocol.channel()

            LOGGER.info(f'Connected {self}')

            # Declare all current subscriptions if reconnecting
            [await sub.declare_on_remote(channel) for sub in self._active]

            while True:
                subscription: EventSubscription = None

                try:
                    await protocol.ensure_open()
                    self._last_ok = True

                    subscription = await asyncio.wait_for(
                        self._pending.get(),
                        timeout=PENDING_WAIT_TIMEOUT.seconds
                    )

                except asyncio.TimeoutError:  # pragma: no cover
                    # Timeout ensures that connection state is checked at least once per timeout
                    continue

                try:
                    await protocol.ensure_open()
                    await subscription.declare_on_remote(channel)
                    self._active.append(subscription)

                except Exception:
                    # Put subscription back in queue
                    # We'll declare it after reconnect
                    self._pending.put_nowait(subscription)
                    raise

        except asyncio.CancelledError:
            raise

        except Exception as ex:
            if self._last_ok:
                warnings.warn(f'Connection error in {self}: {strex(ex)}')
                self._last_ok = False

            await asyncio.sleep(RECONNECT_INTERVAL.seconds)

        finally:
            protocol and await protocol.close()
            transport and transport.close()

    @deprecated(version='0.27.0', reason='Replaced by the mqtt.py module')
    def subscribe(self,
                  exchange_name: str,
                  routing: str,
                  exchange_type: ExchangeType_ = 'topic',
                  on_message: EvtCallbackType_ = None
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

            on_message (EvtCallbackType_, optional):
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
        self._pending.put_nowait(sub)

        if self._has_pending:
            self._has_pending.set()
        else:
            LOGGER.info(f'Deferred event bus subscription: [{sub}]')

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
        self._transport: asyncio.Transport
        self._protocol: aioamqp.AmqpProtocol
        self._channel: aioamqp.channel.Channel
        self._reset()

    @property
    def connected(self):
        return self._transport and self._protocol and self._channel

    def __str__(self):
        return f'<{type(self).__name__} for "{self._host}">'

    def _reset(self):
        self._transport = None
        self._protocol = None
        self._channel = None

    async def _close(self):
        LOGGER.info(f'Closing {self}')
        logging.getLogger('aioamqp.protocol').disabled = True

        try:
            await self._protocol.close(no_wait=True)
            self._transport.close()
        except Exception:
            pass
        finally:
            self._reset()

    async def _ensure_channel(self):
        if not self.connected:
            logging.getLogger('aioamqp.protocol').disabled = False
            self._transport, self._protocol = await aioamqp.connect(
                host=self._host,
                port=self._port,
                login_method='PLAIN',
            )
            self._channel = await self._protocol.channel()

        try:
            await self._protocol.ensure_open()
        except aioamqp.exceptions.AioamqpException:
            await self._close()
            raise

    async def startup(self, app: web.Application):
        pass  # Connections are created when attempting to publish

    async def shutdown(self, app: web.Application):
        await self._close()

    @deprecated(version='0.27.0', reason='Replaced by the mqtt.py module')
    async def publish(self,
                      exchange: str,
                      routing: str,
                      message: Union[str, dict],
                      exchange_type: ExchangeType_ = 'topic',
                      exchange_declare: bool = True):
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

            exchange_declare (bool):
                Whether to declare the exchange.
                This is not required when using built-in exchanges such as 'amq.topic'.
                Defaults to True.

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

        if exchange_declare:
            await self._channel.exchange_declare(
                exchange_name=exchange,
                type_name=exchange_type,
                auto_delete=True,
            )

        await self._channel.basic_publish(
            payload=data,
            exchange_name=exchange,
            routing_key=routing,
        )


##############################################################################
# Module functions
##############################################################################


def setup(app: web.Application):
    """Enables event listening / publishing.

    Args:
        app (web.Application):
            The Aiohttp Application object.
    """
    features.add(app, EventListener(app))
    features.add(app, EventPublisher(app))
    app.router.add_routes(routes)


def get_listener(app: web.Application) -> EventListener:
    """Gets registered EventListener.
    Requires setup() to have been called first.

    Args:
        app (web.Application):
            The Aiohttp Application object.
    """
    return features.get(app, EventListener)


def get_publisher(app: web.Application) -> EventPublisher:
    """Gets registered EventPublisher.
    Requires setup() to have been called first.

    Args:
        app (web.Application):
            The Aiohttp Application object.
    """
    return features.get(app, EventPublisher)


def subscribe(app: web.Application,
              exchange_name: str,
              routing: str,
              exchange_type: ExchangeType_ = 'topic',
              on_message: EvtCallbackType_ = None
              ) -> EventSubscription:
    """Adds a new event subscription to the listener.

    Actual queue declaration to the remote message server is done when connected.
    If the listener is not currently connected, it defers declaration.

    All existing subscriptions are redeclared on the remote if `EventListener`
    loses and recreates the connection.

    Shortcut for `EventListener.subscribe()`
    It requires setup() to have been called.

    Args:
        app (web.Application):
            The Aiohttp Application object.

        exchange_name (str):
            Name of the AMQP exchange. Messages are always published to a specific exchange.

        routing (str):
            Filter messages passing through the exchange.
            A routing key is a '.'-separated string, and accepts '#' and '*' wildcards.

        exchange_type (ExchangeType_, optional):
            If the exchange does not yet exist, it will be created with this type.
            Default is `topic`, acceptable values are `topic`, `fanout`, or `direct`.

        on_message (EvtCallbackType_, optional):
            The function to be called when a new message is received.
            If `on_message` is none, it will default to logging the message.

    Returns:
        EventSubscription:
            The newly created subscription.
            This value can safely be discarded: EventListener keeps its own reference.
    """
    return get_listener(app).subscribe(exchange_name,
                                       routing,
                                       exchange_type,
                                       on_message)


async def publish(app: web.Application,
                  exchange: str,
                  routing: str,
                  message: Union[str, dict],
                  exchange_type: ExchangeType_ = 'topic',
                  exchange_declare: bool = True):
    """
    Publish a new event message.

    Connections are created automatically when calling `publish()`,
    and will attempt to reconnect if connection was lost.

    For more information on publishing AMQP messages,
    see https://www.rabbitmq.com/tutorials/tutorial-three-python.html

    Shortcut for `EventPublisher.publish()`.
    It requires setup() to have been called.

    Args:
        app (web.Application):
            The Aiohttp Application object.

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

        exchange_declare (bool):
            Whether to declare the exchange.
            This is not required when using built-in exchanges such as 'amq.topic'.
            Defaults to True.

    Raises:
        aioamqp.exceptions.AioamqpException:
            * Failed to connect to AMQP host
            * Failed to send message
            * `exchange` already exists, but has a different `exchange_type`
    """
    await get_publisher(app).publish(exchange,
                                     routing,
                                     message,
                                     exchange_type,
                                     exchange_declare)
