"""
Brewblox feature for the aiohttp client
"""

from typing import Optional

from aiohttp import ClientSession, web

from brewblox_service import features


class HTTPClient(features.ServiceFeature):
    def __init__(self, app: web.Application):
        super().__init__(app)
        self._session: Optional[ClientSession] = None

    @property
    def session(self) -> ClientSession:
        return self._session  # type: ignore

    async def startup(self, app: web.Application):
        await self.shutdown(app)
        self._session = await ClientSession(raise_for_status=True).__aenter__()

    async def shutdown(self, app: web.Application):
        if self._session:
            await self._session.__aexit__(None, None, None)
            self._session = None


def setup(app: web.Application):
    features.add(app, HTTPClient(app))


def get_client(app: web.Application) -> HTTPClient:
    return features.get(app, HTTPClient)


def session(app: web.Application) -> ClientSession:
    """Gets web.ClientSession for this app.

    Shortcut for `HTTPClient.session`.
    It requires setup() to have been called().
    """
    return get_client(app).session
