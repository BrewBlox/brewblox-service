"""
Abstract base class for a service that keeps repeating the same action.

This is useful for implementing broadcasting or polling services.

Example use:

    import asyncio
    from datetime import datetime
    from brewblox_service.repeater import RepeaterFeature, features, scheduler

    class Greeter(RepeaterFeature):
        async def prepare(self):
            print('Hello, I am starting now')

        async def run(self):
            await asyncio.sleep(5)
            print(datetime.now())

    def setup(app):
        scheduler.setup(app)
        features.add(app, Greeter(app))

"""

import asyncio
from abc import abstractmethod
from typing import Optional

from aiohttp import web

from brewblox_service import (brewblox_logger, features, models, scheduler,
                              strex)

LOGGER = brewblox_logger(__name__, dedupe=True)


class RepeaterCancelled(Exception):
    """
    This can be raised during either setup() or run() to permanently cancel execution.
    """


class RepeaterFeature(features.ServiceFeature):
    """Base class for Aiohttp handler classes that implement a background task.

    RepeaterFeature wraps the `prepare()` and `run()` functions in an `asyncio.Task`,
    and handles the boilerplate code for creation and cleanup.

    `prepare()` is called once after the background task is started.
    Afterwards, `run()` is called in a loop until the task is stopped.

    The background task is stopped when either:
    - The service stops, and `shutdown()` is called.
    - `end()` is called manually.
    - `prepare()` raises any exception.
    - `prepare()` or `run()` raise a `RepeaterCancelled` exception.

    The `startup()`, `before_shutdown()`, and `shutdown()` functions
    are inherited from `ServiceFeature`.

    During typical app lifetime, functions are called in this order:
    - `startup()`
    - `prepare()`
    - `run()` [repeated until shutdown]
    - `before_shutdown()`
    - `shutdown()`
    """

    def __init__(self, app: web.Application, autostart=True, **kwargs):
        super().__init__(app, **kwargs)
        config: models.ServiceConfig = app['config']

        self._autostart: bool = autostart
        self._task: Optional[asyncio.Task] = None
        self._debug: bool = config.debug

    async def _startup(self, app: web.Application):
        """
        Overrides the private ServiceFeature startup hook.
        This avoids a gotcha where subclasses have to call `super().startup(app)`
        for RepeaterFeature, but not for ServiceFeature.
        """
        await super()._startup(app)
        if self._autostart:
            await self.start()

    async def _shutdown(self, app: web.Application):
        """
        Overrides the private ServiceFeature shutdown hook.
        This avoids a gotcha where subclasses have to call `super().shutdown(app)`
        for RepeaterFeature, but not for ServiceFeature.
        """
        await self.end()
        await super()._shutdown(app)

    async def __repeat(self):
        last_ok = True

        try:
            LOGGER.debug(f'--> prepare {self}')
            await self.prepare()
            LOGGER.debug(f'<-- prepare {self}')

        except asyncio.CancelledError:
            raise

        except RepeaterCancelled:
            LOGGER.info(f'{self} cancelled during prepare().')
            return

        except Exception as ex:
            LOGGER.error(f'{self} error during prepare(): {strex(ex)}')
            raise ex

        while True:
            try:
                await self.run()

                if not last_ok:
                    LOGGER.info(f'{self} resumed OK')
                    last_ok = True

            except asyncio.CancelledError:
                raise

            except RepeaterCancelled:
                LOGGER.info(f'{self} cancelled during run().')
                return

            except Exception as ex:
                # Duplicate log messages are automatically filtered
                LOGGER.error(f'{self} error during run(): {strex(ex, tb=self._debug)}')
                last_ok = False

    @property
    def active(self) -> bool:
        """
        Indicates whether the background task is currently running: not finished, not cancelled.
        """
        return bool(self._task and not self._task.done())

    async def start(self):
        """
        Initializes the background task.
        By default called during startup, but implementations can disable this by using
        `autostart=False` in the constructor.

        Will cancel the previous task if called repeatedly.
        """
        await self.end()
        self._task = await scheduler.create(self.app, self.__repeat())

    async def end(self):
        """
        Ends the background task.
        Always called during shutdown, but can be safely called earlier.
        """
        await scheduler.cancel(self.app, self._task)
        self._task = None

    async def prepare(self):
        """
        One-time preparation.
        Any errors raised here will cause the repeater to abort.
        Raise RepeaterCancelled to abort without error logs.
        """

    @abstractmethod
    async def run(self):
        """
        This function will be called on repeat.
        It is advisable to implement rate limiting through the use of
        `await asyncio.sleep(interval)`
        """
