"""
Master file for pytest fixtures.
Any fixtures declared here are available to all test functions in this directory.
"""


import logging

import pytest

from brewblox_service import service


@pytest.fixture(scope='session', autouse=True)
def log_enabled():
    """Sets log level to DEBUG for all test functions.
    Allows all logged messages to be captured during pytest runs"""
    logging.getLogger().setLevel(logging.DEBUG)


@pytest.fixture
def app_config() -> dict:
    return {
        'name': 'test_app',
        'host': '0.0.0.0',
        'port': 1234,
        'debug': False,
        'output': None,
        'eventbus_host': 'eventbus',
        'eventbus_port': 5672,
    }


@pytest.fixture
def sys_args(app_config) -> list:
    return [str(v) for v in [
        'app_name',
        '--name', app_config['name'],
        '--host', app_config['host'],
        '--port', app_config['port'],
        '--eventbus-host', app_config['eventbus_host'],
        '--eventbus-port', app_config['eventbus_port'],
    ]]


@pytest.fixture
def app(sys_args):
    app = service.create_app('default', raw_args=sys_args[1:])
    return app


@pytest.fixture
def client(app, aiohttp_client, loop):
    """Allows patching the app or aiohttp_client before yielding it.

    Any tests wishing to add custom behavior to app can override the fixture
    """
    return loop.run_until_complete(aiohttp_client(app))
