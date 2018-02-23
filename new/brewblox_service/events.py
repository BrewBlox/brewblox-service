"""
Offers event publishing and subscription for service implementations.
"""

import logging
from concurrent.futures import CancelledError
from typing import Type
import asyncio
import json
from asyncio import Queue

import aio_pika
from aio_pika import ExchangeType
from aiohttp import web

LOGGER = logging.getLogger(__name__)

LISTENER_KEY = 'events.listener'
PUBLISHER_KEY = 'events.publisher'
LOOP_SLEEP_S = 0.01


class EventQueue():
    def __init__(self,
                 exchange_name: str,
                 filter: str,
                 exchange_type=ExchangeType.TOPIC):
        self._routing = filter
        self._exchange_name = exchange_name
        self._exchange_type = exchange_type
        self._queue = None

        async def _on_message(queue, message: str):
            LOGGER.info(f'Unhandled event received on [{queue}]: {message}')

        self.on_message = _on_message
        self.on_json = None

    def __str__(self):
        return f'<{self._routing} @ {self._exchange_name}>'

    @property
    def queue(self) -> Type[aio_pika.Queue]:
        return self._queue

    async def declare(self, connection: Type[aio_pika.Connection]):
        LOGGER.info(f'Declaring event subscription {self}')
        channel = await connection.channel()
        exchange = await channel.declare_exchange(self._exchange_name,
                                                  type=self._exchange_type,
                                                  auto_delete=True)
        self._queue = await channel.declare_queue(self._routing, exclusive=True)
        await self._queue.bind(exchange, self._routing)
        await self.queue.consume(self._relay)

    async def clear(self):
        self._queue = None

    async def _relay(self, message):
        message.ack()
        try:
            if self.on_json:
                await self.on_json(self, json.loads(message.body))
            else:
                await self.on_message(self, message.body.decode())
        except Exception as ex:
            LOGGER.exception(ex)
            raise ex


class EventListener():
    def __init__(self, app):
        self.new_queues = Queue()
        self.queues = set()
        self._connection = None
        self._task = None

        app.on_startup.append(self._startup)
        app.on_cleanup.append(self._cleanup)

    def subscribe(self,
                  app: Type[web.Application],
                  exchange_name: str,
                  queue_name: str,
                  exchange_type=ExchangeType.TOPIC,
                  on_message=None,
                  on_json=None):
        queue = EventQueue(exchange_name, queue_name, exchange_type)

        if on_json:
            queue.on_message = on_json
        elif on_message:
            queue.on_message = on_message

        self.queues.add(queue)
        self.new_queues.put_nowait(queue)
        LOGGER.info(f'New eventbus subscription: [{queue}]')
        return queue

    def unsubscribe(self, app: Type[web.Application], queue: Type[EventQueue]):
        self.queues.remove(queue)
        LOGGER.info(f'Removed eventbus subscription: [{queue}]')

    async def _startup(self, app):
        self._task = app.loop.create_task(self._listen_events(app))

    async def _cleanup(self, app):
        if self._task:
            self._task.cancel()
            await self._task

    async def _listen_events(self, app: Type[web.Application]):
        ready_events = Queue()

        async def _listen(connection):
            try:
                ev = await ready_events.get()
                LOGGER.info(f'Listening for events after connection [{ev}]')
                while not connection.is_closed:
                    new_queue = await self.new_queues.get()
                    await new_queue.declare(connection)
            except RuntimeError as ex:
                LOGGER.warn(f'_listen ran into an error: {ex}')

        def _on_reconnect(connection):
            LOGGER.info('Event listener reconnected')
            ready_events.put_nowait('reconnected')

        def _on_close(connection):
            LOGGER.info('Event listener connection closed.')

        try:
            conn = await aio_pika.connect_robust(loop=app.loop)
            ready_events.put_nowait('connected')
            while True:
                await _listen(conn)
        except CancelledError:
            LOGGER.info('Exiting event listener...')
        except Exception as ex:
            LOGGER.exception(ex)
        finally:
            LOGGER.info('Closing MQ connection')
            if self._connection and not self._connection.is_closed:
                await self._connection.close()


def setup(app: Type[web.Application]):
    logging.getLogger('pika').setLevel(logging.CRITICAL)
    logging.getLogger('pika.adapters.base_connection').setLevel(logging.CRITICAL)
    logging.getLogger('aio_pika.robust_connection').setLevel(logging.CRITICAL)

    app[LISTENER_KEY] = EventListener(app)


def get_listener(app: Type[web.Application]) -> Type[EventListener]:
    return app[LISTENER_KEY]
