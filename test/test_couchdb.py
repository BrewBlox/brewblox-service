"""
Tests brewblox_service.couchdb
"""

import pytest
from aiohttp import web
from aiohttp.client_exceptions import ClientResponseError

from brewblox_service import couchdb, http
from brewblox_service.couchdb import check_remote, read, write

TESTED = couchdb.__name__
SRV_URL = couchdb.COUCH_URL[len('http://'):]
DB_URL = '/sparkbase'
DOC_URL = '/sparkbase/sparkdoc'


@pytest.fixture
def app(app, mocker):
    mocker.patch(TESTED + '.DB_RETRY_INTERVAL_S', 0.01)
    http.setup(app)
    couchdb.setup(app)
    return app


async def test_check_remote(app, client, aresponses):
    for i in range(20):
        aresponses.add(SRV_URL, '/', 'HEAD', web.json_response({}, status=404))
    aresponses.add(SRV_URL, '/', 'HEAD')
    await check_remote(app)


async def test_read(app, client, aresponses):

    # Blank database
    aresponses.add(SRV_URL, '/', 'HEAD')
    aresponses.add(SRV_URL, DB_URL, 'PUT')
    aresponses.add(SRV_URL, DOC_URL, 'GET', web.json_response({}, status=404))
    aresponses.add(SRV_URL, DOC_URL, 'PUT', web.json_response({'rev': 'rev_read'}))
    assert await read(app, 'sparkbase', 'sparkdoc', [1, 2]) == ('rev_read', [1, 2])

    # Retry contact server, content in database
    for i in range(20):
        aresponses.add(SRV_URL, '/', 'HEAD', web.json_response({}, status=404))
    aresponses.add(SRV_URL, '/', 'HEAD')
    aresponses.add(SRV_URL, DB_URL, 'PUT', web.json_response({}, status=412))
    aresponses.add(SRV_URL, DOC_URL, 'GET', web.json_response({'_rev': 'rev_read', 'data': [2, 1]}))
    aresponses.add(SRV_URL, DOC_URL, 'PUT', web.json_response({}, status=409))
    assert await read(app, 'sparkbase', 'sparkdoc', []) == ('rev_read', [2, 1])


async def test_read_errors(app, client, aresponses):
    with pytest.raises(ClientResponseError):
        aresponses.add(SRV_URL, '/', 'HEAD')
        aresponses.add(SRV_URL, DB_URL, 'PUT', web.json_response({}, status=404))
        await read(app, 'sparkbase', 'sparkdoc', [])

    with pytest.raises(ClientResponseError):
        aresponses.add(SRV_URL, '/', 'HEAD')
        aresponses.add(SRV_URL, DB_URL, 'PUT')
        aresponses.add(SRV_URL, DOC_URL, 'PUT', web.json_response({}, status=404))  # unexpected
        aresponses.add(SRV_URL, DOC_URL, 'GET', web.json_response({}, status=404))
        await read(app, 'sparkbase', 'sparkdoc', [])

    with pytest.raises(ClientResponseError):
        aresponses.add(SRV_URL, '/', 'HEAD')
        aresponses.add(SRV_URL, DB_URL, 'PUT')
        aresponses.add(SRV_URL, DOC_URL, 'PUT', web.json_response({}, status=412))
        aresponses.add(SRV_URL, DOC_URL, 'GET', web.json_response({}, status=500))  # unexpected
        await read(app, 'sparkbase', 'sparkdoc', [])

    with pytest.raises(ValueError):
        aresponses.add(SRV_URL, '/', 'HEAD')
        aresponses.add(SRV_URL, DB_URL, 'PUT')
        # Either get or put must return an ok value
        aresponses.add(SRV_URL, DOC_URL, 'PUT', web.json_response({}, status=409))
        aresponses.add(SRV_URL, DOC_URL, 'GET', web.json_response({}, status=404))
        await read(app, 'sparkbase', 'sparkdoc', [])


async def test_write(app, client, aresponses):
    aresponses.add(
        SRV_URL, f'{DOC_URL}?rev=revy', 'PUT',
        web.json_response({'rev': 'rev_write'}), match_querystring=True)
    assert await write(app, 'sparkbase', 'sparkdoc', 'revy', [1, 2]) == 'rev_write'
