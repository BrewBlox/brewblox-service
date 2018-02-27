"""
Tests brewblox_service.announcer.py
"""

from brewblox_service import announcer
from aiohttp import ClientSession
from aioresponses import aioresponses
from unittest.mock import ANY

TESTED = announcer.__name__


async def test_create_proxy_spec(app):
    spec = await announcer.create_proxy_spec('test_name', 'localhost', 1234)

    assert spec == {
        'name': 'test_name',
        'active': True,
        'proxy': {
            'strip_path': False,
            'append_path': True,
            'listen_path': '/test_name/*',
            'methods': ANY,
            'upstreams': {
                'balancing': 'roundrobin',
                'targets': [{'target': 'http://localhost:1234'}]
            }
        },
        'health_check': {
            'url': 'http://localhost:1234/test_name/_service/status'
        }
    }


async def test_auth_header():
    session = ClientSession()
    with aioresponses() as res:
        res.post('http://gateway:4321/login', payload=dict(access_token='tokkie'))

        headers = await announcer.auth_header(session, 'http://gateway:4321')
        assert headers == {'authorization': 'Bearer tokkie'}
        assert len(res.requests) == 1


async def test_announce_err(mocker, app):
    log_mock = mocker.patch(TESTED + '.LOGGER')
    await announcer.announce(app)
    assert log_mock.warn.call_count == 1


async def test_announce(app):
    with aioresponses() as res:
        res.post('http://gatewayaddr:1234/login', payload=dict(access_token='tokkie'))
        res.delete('http://gatewayaddr:1234/apis/test_app', status=200)
        res.post('http://gatewayaddr:1234/apis', status=200)

        await announcer.announce(app)
        assert len(res.requests) == 3
