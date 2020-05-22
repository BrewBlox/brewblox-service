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

from brewblox_service import brewblox_logger, features, scheduler, strex

LOGGER = brewblox_logger(__name__)


class RepeaterCancelled(Exception):
    """
    This can be raised during either setup() or run() to permanently cancel execution.
    """


class RepeaterFeature(features.ServiceFeature):

    def __init__(self, app: web.Application):
        super().__init__(app)
        self._task: Optional[asyncio.Task] = None

    @property
    def active(self) -> bool:
        """
        Indicates whether the background task is currently running: not finished, not cancelled.
        """
        return bool(self._task and not self._task.done())

    async def startup(self, app: web.Application):
        await self.shutdown(app)
        await self.start()

    async def shutdown(self, app: web.Application):
        await self.end()

    async def __repeat(self):
        last_ok = True

        try:
            await self.prepare()

        except asyncio.CancelledError:
            raise

        except RepeaterCancelled:
            LOGGER.info(f'{self} cancelled during setup.')
            return

        except Exception as ex:
            LOGGER.error(f'{self} error during setup: {strex(ex)}')
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
                LOGGER.info(f'{self} cancelled during runtime.')
                return

            except Exception as ex:
                # Only log the first error to prevent log spam
                if last_ok:
                    LOGGER.error(f'{self} error during runtime: {strex(ex)}')
                    last_ok = False

    async def start(self):
        """
        Initializes the repeater task.
        By default called during startup(), but implementations can choose to override this.
        Will cancel the previous task if called repeatedly.
        """
        await self.end()
        self._task = await scheduler.create(self.app, self.__repeat())

    async def end(self):
        """
        Ends the repeater task.
        Always called during shutdown(), but can be safely called earlier.
        """
        await scheduler.cancel(self.app, self._task)
        self._task = None

    @abstractmethod
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
        `await asyncio.sleep()`
        """
