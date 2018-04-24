"""
Generic superclass for aiohttp handlers with startup/cleanup hooks.
"""

import asyncio
from abc import ABC, abstractmethod

from aiohttp import web


class ServiceHandler(ABC):

    def __init__(self, app: web.Application=None):
        if app:
            app.on_startup.append(self._startup)
            app.on_cleanup.append(self._cleanup)

    async def _startup(self, app: web.Application):
        await self.start(app.loop)

    async def _cleanup(self, app: web.Application):
        await self.close()

    @abstractmethod
    async def start(loop: asyncio.BaseEventLoop):
        pass  # pragma: no cover

    @abstractmethod
    async def close():
        pass  # pragma: no cover
