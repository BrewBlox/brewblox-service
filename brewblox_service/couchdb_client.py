import asyncio
from typing import Any, Awaitable, Tuple

from aiohttp import client_exceptions, web

from brewblox_service import brewblox_logger, features, http_client

LOGGER = brewblox_logger(__name__)

DB_RETRY_INTERVAL_S = 1
COUCH_URL = 'http://datastore:5984'


def setup(app: web.Application):
    features.add(app, CouchDBClient(app))


def get_client(app: web.Application) -> 'CouchDBClient':
    return features.get(app, CouchDBClient)


class CouchDBClient(features.ServiceFeature):

    def __str__(self):
        return f'<{type(self).__name__} for {COUCH_URL}>'

    async def startup(self, app: web.Application):
        pass

    async def shutdown(self, app: web.Application):
        pass

    async def check_remote(self):
        session = http_client.get_client(self.app).session
        num_attempts = 0
        while True:
            try:
                await session.head(COUCH_URL, raise_for_status=True)
            except asyncio.CancelledError:  # pragma: no cover
                raise
            except Exception:
                num_attempts += 1
                if num_attempts % 10 == 0:
                    LOGGER.info(f'{self} Waiting for datastore...')
                await asyncio.sleep(DB_RETRY_INTERVAL_S)
            else:
                return

    async def read(self, database: str, document: str, default_data: Any) -> Awaitable[Tuple[str, Any]]:
        db_url = f'{COUCH_URL}/{database}'
        document_url = f'{db_url}/{document}'
        session = http_client.get_client(self.app).session

        async def ensure_database():
            try:
                await session.put(db_url)
                LOGGER.info(f'{self} New database created ({database})')

            except client_exceptions.ClientResponseError as ex:
                if ex.status != 412:  # Already exists
                    raise ex

        async def create_document():
            try:
                resp = await session.put(document_url, json={'data': default_data})
                resp_content = await resp.json()

                rev = resp_content['rev']
                data = default_data
                LOGGER.info(f'{self} New document created ({document})')
                return rev, data

            except client_exceptions.ClientResponseError as ex:
                if ex.status != 409:  # Conflict: already exists
                    raise ex

        async def read_document():
            try:
                resp = await session.get(document_url)
                resp_content = await resp.json()

                rev = resp_content['_rev']
                data = resp_content['data']
                LOGGER.info(f'{self} Existing document found ({document})')
                return rev, data

            except client_exceptions.ClientResponseError as ex:
                if ex.status != 404:
                    raise ex

        try:
            await self.check_remote()
            await ensure_database()
            read_result, create_result = await asyncio.gather(read_document(), create_document())
            (rev, data) = read_result or create_result or (None, None)
            if rev is None:
                raise ValueError('Data was neither read nor created')
            return rev, data

        except asyncio.CancelledError:  # pragma: no cover
            raise

        except Exception as ex:
            LOGGER.error(f'{self} {type(ex).__name__}({ex})')
            raise ex

    async def write(self, database: str, document: str, rev: str, data: Any) -> Awaitable[str]:
        kwargs = {
            'url': f'{COUCH_URL}/{database}/{document}',
            'json': {'data': data},
            'params': [('rev', rev)],
        }

        resp = await http_client.get_client(self.app).session.put(**kwargs)
        resp_content = await resp.json()
        return resp_content['rev']
