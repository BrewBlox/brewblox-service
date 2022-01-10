"""
Tests brewblox_service.testing
"""

from unittest.mock import Mock

import pytest
from aiohttp import web

from brewblox_service import service, testing

routes = web.RouteTableDef()


@routes.view('/_testerror')
class PublishView(web.View):
    async def post(self):
        raise RuntimeError('BEEP BOOP')


@routes.view('/_service/status')
class HealthcheckView(web.View):
    async def get(self):
        return web.json_response({'status': 'ok'})


@pytest.fixture
def app(app: web.Application, mocker):
    app.add_routes(routes)
    service.furnish(app)
    return app


async def test_response(app, client):
    await testing.response(client.get('/test_app/_service/status'))
    with pytest.raises(AssertionError):
        await testing.response(client.get('/test_app/_service/status'), 400)
    await testing.response(client.get('/test_app/_testerror'), 405)
    assert 'BEEP BOOP' in await testing.response(client.post('/test_app/_testerror'), 500)


def test_matching():
    obj = testing.matching(r'.art')
    assert obj == 'cart'
    assert obj == 'part'
    assert obj != 'car'
    assert obj != ''

    mock = Mock()
    mock('fart')
    mock.assert_called_with(obj)
