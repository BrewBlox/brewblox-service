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
    logging.captureWarnings(True)


@pytest.fixture
def app_config() -> dict:
    return {
        'name': 'test_app',
        'host': '0.0.0.0',
        'port': 1234,
        'debug': False,
        'mqtt_protocol': 'mqtt',
        'mqtt_host': 'eventbus',
        'mqtt_port': 1883,
        'mqtt_path': '/eventbus',
        'history_topic': '/brewcast/history',
        'state_topic': '/brewcast/state',
    }


@pytest.fixture
def sys_args(app_config) -> list:
    return [str(v) for v in [
        'app_name',
        '--name', app_config['name'],
        '--host', app_config['host'],
        '--port', app_config['port'],
        '--mqtt-protocol', app_config['mqtt_protocol'],
        '--mqtt-host', app_config['mqtt_host'],
        '--mqtt-port', app_config['mqtt_port'],
        '--mqtt-path', app_config['mqtt_path'],
        '--history-topic', app_config['history_topic'],
        '--state-topic', app_config['state_topic'],
    ]]


@pytest.fixture
def app(sys_args):
    app = service.create_app('default', raw_args=sys_args[1:])
    return app


@pytest.fixture
async def client(app, aiohttp_client, aiohttp_server):
    """Allows patching the app or aiohttp_client before yielding it.

    Any tests wishing to add custom behavior to app can override the fixture
    """
    return await aiohttp_client(await aiohttp_server(app))


@pytest.fixture(scope='session')
def find_free_port():
    """
    Returns a factory that finds the next free port that is available on the OS
    This is a bit of a hack, it does this by creating a new socket, and calling
    bind with the 0 port. The operating system will assign a brand new port,
    which we can find out using getsockname(). Once we have the new port
    information we close the socket thereby returning it to the free pool.
    This means it is technically possible for this function to return the same
    port twice (for example if run in very quick succession), however operating
    systems return a random port number in the default range (1024 - 65535),
    and it is highly unlikely for two processes to get the same port number.
    In other words, it is possible to flake, but incredibly unlikely.
    """

    def _find_free_port():
        import socket

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(('0.0.0.0', 0))
        portnum = s.getsockname()[1]
        s.close()

        return portnum

    return _find_free_port
