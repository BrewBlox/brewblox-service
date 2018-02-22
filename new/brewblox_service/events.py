"""
Offers event publishing and subscription for service implementations.
"""

import logging
from concurrent.futures import CancelledError
from typing import Type
import asyncio
import json

import aio_pika
from aio_pika import ExchangeType
from aiohttp import web

LOGGER = logging.getLogger(__name__)
routes = web.RouteTableDef()

QUEUE_COL_KEY = 'events.queues'
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
        if self._queue is None:
            LOGGER.info(f'Declaring event subscription {self}')
            channel = await connection.channel()
            exchange = await channel.declare_exchange(self._exchange_name,
                                                      type=self._exchange_type,
                                                      auto_delete=True)
            self._queue = await channel.declare_queue(self._routing, exclusive=True)
            await self._queue.bind(exchange, self._routing)

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

    async def get(self):
        await self.queue.consume(self._relay)


def setup(app: Type[web.Application]):
    async def _startup(app):
        app[LISTENER_KEY] = app.loop.create_task(_listen_events(app))

    async def _cleanup(app):
        if LISTENER_KEY in app:
            task = app[LISTENER_KEY]
            task.cancel()
            await task

    app[QUEUE_COL_KEY] = set()
    app.on_startup.append(_startup)
    app.on_cleanup.append(_cleanup)
    app.router.add_routes(routes)


def subscribe(app: Type[web.Application],
              exchange_name: str,
              queue_name: str,
              exchange_type=ExchangeType.TOPIC,
              on_message=None,
              on_json=None) -> Type[EventQueue]:
    queue = EventQueue(exchange_name, queue_name, exchange_type)

    if on_json:
        queue.on_message = on_json
    elif on_message:
        queue.on_message = on_message

    app[QUEUE_COL_KEY].add(queue)
    LOGGER.info(f'New eventbus subscription: [{queue}]')
    return queue


def unsubscribe(app: Type[web.Application], queue: Type[EventQueue]):
    app[QUEUE_COL_KEY].remove(queue)
    LOGGER.info(f'Removed eventbus subscription: [{queue}]')


async def _listen_events(app: Type[web.Application]):
    try:
        for connection in aio_pika.connect_robust(loop=app.loop):
            LOGGER.info('reading queues')
            while True:
                # Avoid idle loops going crazy
                await asyncio.sleep(LOOP_SLEEP_S)

                for queue in app[QUEUE_COL_KEY]:
                    await queue.declare(connection)
                    await queue.get()

            # [q.clear() for q in app[QUEUE_COL_KEY]]
        LOGGER.info('queues end')
        # TODO
    except CancelledError:
        LOGGER.info('Exiting event listener...')
    except Exception as ex:
        pass
        # LOGGER.exception(ex)
    finally:
        pass
        # connection.is_closed or await connection.close()


@routes.post('/events/subscribe')
async def post_subscribe(request: Type[web.Request]) -> Type[web.Response]:
    args = await request.json()
    subscribe(request.app, args['exchange'], args['queue'])
    return web.json_response(dict(ok=True))
