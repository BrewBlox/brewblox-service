"""
Background task scheduling.
"""

import asyncio
from contextlib import suppress
from typing import Any, Coroutine, Optional, Set

from aiohttp import web

from brewblox_service import brewblox_logger, features

CLEANUP_INTERVAL_S = 300


LOGGER = brewblox_logger(__name__)


class TaskScheduler(features.ServiceFeature):

    def __init__(self, app: web.Application):
        super().__init__(app)
        self._tasks: Set[asyncio.Task] = set()

    async def startup(self, *_):
        await self.create(self._cleanup())

    async def shutdown(self, *_):
        for task in self._tasks:
            task.cancel()
        await asyncio.wait(self._tasks)
        self._tasks.clear()

    async def _cleanup(self):
        """
        Periodically removes completed tasks from the collection,
        allowing fire-and-forget tasks to be garbage collected.

        This does not delete the task object, it merely removes the reference in the scheduler.
        """
        while True:
            await asyncio.sleep(CLEANUP_INTERVAL_S)
            self._tasks = set(t for t in self._tasks if not t.done())

    async def create(self,
                     coro: Coroutine,
                     name: str = None,
                     ) -> asyncio.Task:
        try:
            task = asyncio.create_task(coro, name=name)
        except TypeError:  # pragma: no cover
            # The name argument was introduced in Python 3.8
            task = asyncio.create_task(coro)
        LOGGER.debug(f'Scheduled {task}')
        self._tasks.add(task)
        return task

    async def cancel(self,
                     task: asyncio.Task,
                     wait_for: bool = True,
                     ) -> Optional[Any]:
        if task is None:
            return

        task.cancel()

        with suppress(KeyError):
            self._tasks.remove(task)

        retv = None

        with suppress(Exception, asyncio.CancelledError):
            if wait_for:
                retv = await task

        LOGGER.debug(f'Cancelled: {task}')
        return retv


def setup(app: web.Application):
    """Registers scheduler functionality with Application.

    Args:
        app (web.Application):
            The Aiohttp Application object.
    """
    features.add(app, TaskScheduler(app))


def get_scheduler(app: web.Application) -> TaskScheduler:
    """Gets the default TaskScheduler object

    Args:
        app (web.Application):
            The Aiohttp Application object.
    """
    return features.get(app, TaskScheduler)


async def create(app: web.Application,
                 coro: Coroutine,
                 name: str = None
                 ) -> asyncio.Task:
    """
    Starts execution of a coroutine.

    The created asyncio.Task is returned, and added to managed tasks.
    The scheduler guarantees that it is cancelled during application shutdown,
    regardless of whether it was already cancelled manually.

    Shortcut for `TaskScheduler.create(coro)`
    Requires setup() to have been called.

    Args:
        coro (Coroutine):
            The coroutine to be wrapped in a task, and executed.
        name (str):
            Custom name for the created task.

    Returns:
        asyncio.Task: An awaitable Task object.
            During Aiohttp shutdown, the scheduler will attempt to cancel and await this task.
            The task can be safely cancelled manually, or using `TaskScheduler.cancel(task)`.

    Example:

        import asyncio
        from datetime import datetime
        from brewblox_service import scheduler, service


        async def current_time(interval):
            while True:
                await asyncio.sleep(interval)
                print(datetime.now())


        async def start(app):
            await scheduler.create(app, current_time(interval=2))


        app = service.create_app(default_name='example')

        scheduler.setup(app)
        app.on_startup.append(start)

        service.furnish(app)
        service.run(app)
    """
    return await get_scheduler(app).create(coro, name=name)


async def cancel(app: web.Application,
                 task: asyncio.Task,
                 wait_for: bool = True,
                 ) -> Optional[Any]:
    """
    Cancels and waits for an `asyncio.Task` to finish.
    Removes it from the collection of managed tasks.

    Shortcut for `TaskScheduler.cancel(task)`.
    Requires setup() to have been called.

    Args:
        task (asyncio.Task):
            The to be cancelled task.
            It is not required that the task was was created with `TaskScheduler.create()`.

        wait_for (bool, optional):
            Whether to wait for the task to finish execution.
            If falsey, this function returns immediately after cancelling the task.

    Returns:
        Any: The return value of `task`. None if `wait_for` is falsey.

    Example:

        import asyncio
        from datetime import datetime
        from brewblox_service import scheduler, service

        async def current_time(interval):
            while True:
                await asyncio.sleep(interval)
                print(datetime.now())


        async def stop_after(app, task, duration):
            await asyncio.sleep(duration)
            await scheduler.cancel(app, task)
            print('stopped!')


        async def start(app):
            # Start first task
            task = await scheduler.create(app, current_time(interval=2))

            # Start second task to stop the first
            await scheduler.create(app, stop_after(app, task, duration=10))


        app = service.create_app(default_name='example')

        scheduler.setup(app)
        app.on_startup.append(start)

        service.furnish(app)
        service.run(app)
    """
    return await get_scheduler(app).cancel(task, wait_for=wait_for)
