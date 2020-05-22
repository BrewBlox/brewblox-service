import asyncio
from typing import Any, Optional, Tuple

from aiohttp import client_exceptions, web

from brewblox_service import brewblox_logger, features, http

LOGGER = brewblox_logger(__name__)

DB_RETRY_INTERVAL_S = 1
COUCH_URL = 'http://datastore:5984'


class CouchDBClient(features.ServiceFeature):

    def __str__(self):
        return f'<{type(self).__name__} for {COUCH_URL}>'

    async def startup(self, app: web.Application):
        pass

    async def shutdown(self, app: web.Application):
        pass

    async def check_remote(self):
        session = http.session(self.app)
        num_attempts = 0
        while True:
            try:
                await session.head(COUCH_URL, raise_for_status=True)
                break
            except Exception:
                num_attempts += 1
                if num_attempts % 10 == 0:
                    LOGGER.info(f'{self} Waiting for datastore...')
                await asyncio.sleep(DB_RETRY_INTERVAL_S)

    async def read(self,
                   database: str,
                   document: str,
                   default_data: Any,
                   ) -> Tuple[str, Any]:
        db_url = f'{COUCH_URL}/{database}'
        document_url = f'{db_url}/{document}'
        session = http.session(self.app)

        async def ensure_database():
            try:
                await session.put(db_url)
                LOGGER.info(f'{self} New database created ({database})')

            except client_exceptions.ClientResponseError as ex:
                if ex.status != 412:  # Already exists
                    raise ex

        async def create_document() -> Optional[Tuple[str, Any]]:
            try:
                resp = await session.put(document_url, json={'data': default_data})
                resp_content = await resp.json()

                rev = resp_content['rev']
                data = default_data
                LOGGER.info(f'{self} New document created ({document})')
                return rev, data

            except client_exceptions.ClientResponseError as ex:
                if ex.status == 409:  # Conflict: already exists
                    return None
                else:
                    raise ex

        async def read_document() -> Optional[Tuple[str, Any]]:
            try:
                resp = await session.get(document_url)
                resp_content = await resp.json()

                rev = resp_content['_rev']
                data = resp_content['data']
                LOGGER.info(f'{self} Existing document found ({document})')
                return rev, data

            except client_exceptions.ClientResponseError as ex:
                if ex.status == 404:
                    return None
                else:
                    raise ex

        try:
            await self.check_remote()
            await ensure_database()
            read_result, create_result = await asyncio.gather(read_document(), create_document())
            (rev, data) = read_result or create_result or (None, None)
            if rev is None:
                raise ValueError('Data was neither read nor created')
            return rev, data

        except Exception as ex:
            LOGGER.error(f'{self} {type(ex).__name__}({ex})')
            raise ex

    async def write(self, database: str, document: str, rev: str, data: Any) -> str:
        resp = await http.session(self.app).put(
            url=f'{COUCH_URL}/{database}/{document}',
            json={'data': data},
            params=[('rev', rev)]
        )
        resp_content = await resp.json()
        return resp_content['rev']


def setup(app: web.Application):
    """Enables CouchDB interaction.

    Args:
        app (web.Application):
            The Aiohttp Application object.
    """
    features.add(app, CouchDBClient(app))


def get_client(app: web.Application) -> CouchDBClient:
    """Gets registered CouchDBClient.
    Requires setup() to have been called first.

    Args:
        app (web.Application):
            The Aiohttp Application object.
    """
    return features.get(app, CouchDBClient)


async def check_remote(app: web.Application):
    """Waits for the remote datastore to be available

    Shortcut for `CouchDBClient.check_remote()`

    Args:
        app (web.Application):
            The Aiohttp Application object.
    """
    await get_client(app).check_remote()


async def read(app: web.Application,
               database: str,
               document: str,
               default_data: Any
               ) -> Tuple[str, Any]:
    """Fetches data from CouchDB document.

    If the database does not exist, it will be created.
    If the document does not exist, it will be created, and filled with `default_data`.

    Shortcut for `CouchDBClient.read()`
    It requires setup() to have been called.

    Args:
        app (web.Application):
            The Aiohttp Application object.

        database (str):
            The CouchDB database name.

        document (str):
            The document name in the database.

        default_data (Any):
            If the document does not exist, it will be initialized with this.

    Returns:
        (revision ID, data):
            The revision ID is required for later writing data to the document.
            Data is document content, and equals `default_data` if the document was created.
    """
    return await get_client(app).read(database,
                                      document,
                                      default_data)


async def write(app: web.Application,
                database: str,
                document: str,
                rev: str,
                data: Any
                ) -> str:
    """Writes data to an existing CouchDB document.

    Shortcut for `CouchDBClient.write()`
    It requires setup() to have been called.

    Args:
        app (web.Application):
            The Aiohttp Application object.

        database (str):
            The CouchDB database name.

        document (str):
            The document name in the database.

        rev (str):
            The document revision ID.
            It must match that of the last update to the document.

        data (any):
            Document content.

    Returns:
        str:
            The new revision ID.
    """
    return await get_client(app).write(database,
                                       document,
                                       rev,
                                       data)
