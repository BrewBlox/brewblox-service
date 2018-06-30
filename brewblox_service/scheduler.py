"""
Functionality for background tasks.
"""

import asyncio
from contextlib import suppress
from typing import Any, Coroutine, Set

from aiohttp import web
from brewblox_service import features

CLEANUP_INTERVAL_S = 300


def setup(app: web.Application):
    features.add(app, TaskScheduler(app))


def get_scheduler(app: web.Application):
    return features.get(app, TaskScheduler)


async def create_task(app: web.Application,
                      coro: Coroutine,
                      loop: asyncio.BaseEventLoop=None
                      ) -> asyncio.Task:
    return await get_scheduler(app).create(coro, loop)


async def cancel_task(app: web.Application,
                      task: asyncio.Task,
                      wait_for: bool=True
                      ) -> Any:
    return await get_scheduler(app).cancel(task, wait_for)


class TaskScheduler(features.ServiceFeature):

    def __init__(self, app: web.Application):
        super().__init__(app)
        self._tasks: Set[asyncio.Task] = set()

    async def startup(self, *_):
        await self.create(self._cleanup())

    async def shutdown(self, *_):
        [task.cancel() for task in self._tasks]
        await asyncio.wait(self._tasks)
        self._tasks.clear()

    async def _cleanup(self):
        while True:
            await asyncio.sleep(CLEANUP_INTERVAL_S)
            self._tasks = {t for t in self._tasks if not t.done()}

    async def create(self, coro: Coroutine, loop: asyncio.BaseEventLoop=None) -> asyncio.Task:
        loop = loop or asyncio.get_event_loop()
        task = loop.create_task(coro)
        self._tasks.add(task)
        return task

    async def cancel(self, task: asyncio.Task, wait_for: bool=True) -> Any:
        task.cancel()

        with suppress(KeyError):
            self._tasks.remove(task)

        with suppress(Exception):
            return (await task) if wait_for else None
