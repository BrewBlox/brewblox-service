"""
Tests brewblox_service.testing
"""

from subprocess import check_output
from unittest.mock import Mock

import pytest
from aiohttp import web

from brewblox_service import testing

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
async def app_setup(app: web.Application):
    app.add_routes(routes)


async def test_response(app, client):
    await testing.response(client.get('/_service/status'))
    with pytest.raises(AssertionError):
        await testing.response(client.get('/_service/status'), 400)
    await testing.response(client.get('/_testerror'), 405)
    assert 'BEEP BOOP' in await testing.response(client.post('/_testerror'), 500)


def test_matching():
    obj = testing.matching(r'.art')
    assert obj == 'cart'
    assert obj == 'part'
    assert obj != 'car'
    assert obj != ''

    mock = Mock()
    mock('fart')
    mock.assert_called_with(obj)


def test_docker_container():
    def active_containers():
        return check_output(['docker', 'ps', '--format={{.Names}}']).decode()

    with pytest.raises(RuntimeError):
        with testing.docker_container(
            name='broker-test-broker',
            ports={'mqtt': 1883},
            args=['ghcr.io/brewblox/mosquitto:develop'],
        ) as ports:
            assert 'broker-test-broker' in active_containers()
            assert ports['mqtt'] != 1883
            raise RuntimeError('Boo!')

    assert 'broker-test-broker' not in active_containers()
