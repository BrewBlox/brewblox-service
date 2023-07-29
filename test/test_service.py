"""
Test functions in brewblox_service.service.py
"""

import asyncio
from unittest.mock import ANY, call

import pytest
from aiohttp import web, web_exceptions
from aiohttp.client_exceptions import ServerDisconnectedError
from aiohttp_pydantic.oas.typing import r200
from aiohttp_pydantic.view import PydanticView
from pydantic import BaseModel

from brewblox_service import features, models, service, testing

routes = web.RouteTableDef()
TESTED = service.__name__


class DummyFeature(features.ServiceFeature):
    async def startup(self, app):
        pass

    async def shutdown(self, app):
        pass


class MultiplyArgs(BaseModel):
    a: float
    b: float


class MultiplyResult(MultiplyArgs):
    result: float


class ExtendedConfig(models.BaseServiceConfig):
    test: bool


@routes.view('/status')
class HealthcheckView(web.View):
    async def get(self):
        return web.json_response({'status': 'ok'})


@routes.view('/multiply')
class MultiplyView(PydanticView):
    async def post(self, args: MultiplyArgs) -> r200[MultiplyResult]:
        result = MultiplyResult(
            a=args.a,
            b=args.b,
            result=args.a*args.b,
        )
        return web.json_response(result.dict())


@routes.view('/runtime_error')
class RuntimeErrorView(web.View):
    async def get(self):
        raise RuntimeError()


@routes.view('/auth_error')
class UnauthorizedErrorView(web.View):
    async def get(self):
        raise web_exceptions.HTTPUnauthorized(reason='')


@routes.view('/cancelled_error')
class CancelledErrorView(web.View):
    async def get(self):
        raise asyncio.CancelledError()


@pytest.fixture
async def app_setup(app: web.Application, mocker):
    app.router.add_static(prefix='/static', path='/usr')
    features.add(app, DummyFeature(app))
    app.add_routes(routes)


def test_parse_args():
    # test defaults
    parser = service.create_parser('brewblox')
    args = parser.parse_args([])
    assert args.port == 5000
    assert not args.debug
    assert args.host == '0.0.0.0'
    assert args.name == 'brewblox'

    # test host
    args = parser.parse_args(['-H', 'host_name'])
    assert args.host == 'host_name'

    # test name
    args = parser.parse_args(['-n', 'service_name'])
    assert args.name == 'service_name'

    # test port
    args = parser.parse_args(['-p', '1234'])
    assert args.port == 1234

    # test debug mode
    args = parser.parse_args(['--debug'])
    assert args.debug


def test_init_logging(mocker):
    log_mock = mocker.patch(TESTED + '.logging')

    args = service.create_parser('brewblox').parse_args([])
    service._init_logging(args)

    assert log_mock.basicConfig.call_count == 1

    log_mock.getLogger.assert_has_calls([
        call('aiohttp.access'),
        call().setLevel(log_mock.WARN),
    ])


def test_no_logging_mute(mocker):
    log_mock = mocker.patch(TESTED + '.logging')

    args = service.create_parser('brewblox').parse_args(['--debug'])
    service._init_logging(args)

    assert log_mock.getLogger.call_count == 0


def test_create_app(sys_args, app_config, mocker):
    raw_args = sys_args[1:] + ['--unknown', 'really']
    m_error = mocker.patch(TESTED + '.LOGGER.error')
    parser = service.create_parser('brewblox')
    config = service.create_config(parser, raw_args=raw_args)
    app = service.create_app(config)

    assert app is not None
    assert app['config'] == app_config
    assert config == app_config
    m_error.assert_called_once_with(testing.matching(r".*\['--unknown', 'really'\]"))


def test_create_no_args(sys_args, app_config, mocker):
    mocker.patch(TESTED + '.sys.argv', sys_args)

    parser = service.create_parser('default')
    config = service.create_config(parser)
    app = service.create_app(config)

    assert app['config'] == app_config


def test_create_w_parser(sys_args, app_config, mocker):
    parser = service.create_parser('brewblox')
    parser.add_argument('-t', '--test', action='store_true')

    sys_args += ['-t']
    config = service.create_config(parser, model=ExtendedConfig, raw_args=sys_args[1:])
    assert config.test is True


async def test_cors(app, client, mocker):
    res = await client.get('/status')
    assert res.status == 200
    assert 'Access-Control-Allow-Origin' in res.headers
    assert await res.json() == {'status': 'ok'}

    # CORS preflight
    res = await client.options('/status')
    assert res.status == 200
    assert 'Access-Control-Allow-Origin' in res.headers

    res = await client.get('/nonsense')
    assert res.status == 404
    assert 'Access-Control-Allow-Origin' in res.headers

    res = await client.get('/runtime_error')
    assert res.status == 500
    assert 'Access-Control-Allow-Origin' in res.headers

    res = await client.get('/auth_error')
    assert res.status == 401
    assert 'Access-Control-Allow-Origin' in res.headers

    with pytest.raises(ServerDisconnectedError):
        await client.get('/cancelled_error')


async def test_multiply(app, client):
    res = await testing.response(client.post('/multiply', json={'a': 3, 'b': 2}))
    assert res == {'a': 3, 'b': 2, 'result': pytest.approx(6)}

    res = await testing.response(client.post('/multiply', json={'a': 3, 'b': 2, 'c': 3}))
    assert res == {'a': 3, 'b': 2, 'result': pytest.approx(6)}

    await testing.response(client.post('/multiply', json={}), status=400)


async def test_run_app(app, mocker):
    run_mock = mocker.patch(TESTED + '.web.run_app')

    async def setup_func():
        features.add(app, DummyFeature(app))

    service.run_app(app)
    run_mock.assert_called_with(ANY, host='0.0.0.0', port=1234)
    assert await run_mock.call_args[0][0] == app

    service.run_app(app, setup=setup_func())
    run_mock.assert_called_with(ANY, host='0.0.0.0', port=1234)
    assert await run_mock.call_args[0][0] == app
    assert features.get(app, DummyFeature)  # Checks whether setup_func() was awaited

    service.run_app(app, listen_http=False)
    run_mock.assert_called_with(ANY, path=testing.matching(r'/tmp/.+/dummy.sock'))
    assert await run_mock.call_args[0][0] == app
