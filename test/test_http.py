"""
Tests brewblox_service.http
"""

import pytest
from aiohttp import web
from aresponses import ResponsesMockServer

from brewblox_service import http

TESTED = http.__name__


@pytest.fixture
async def app_setup(app, mocker):
    http.setup(app)


async def test_session(app, client, aresponses: ResponsesMockServer):
    aresponses.add(path_pattern='/endpoint',
                   method_pattern='POST',
                   response=web.json_response({'ok': True}))
    resp = await http.session(app).post('http://wherever/endpoint', json={})
    assert (await resp.json()) == {'ok': True}
    aresponses.assert_all_requests_matched()
