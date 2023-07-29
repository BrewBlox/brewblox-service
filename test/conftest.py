"""
Master file for pytest fixtures.
Any fixtures declared here are available to all test functions in this directory.
"""


import logging

import pytest
from aiohttp import test_utils

from brewblox_service import models, service


@pytest.fixture(scope='session', autouse=True)
def log_enabled():
    """Sets log level to DEBUG for all test functions.
    Allows all logged messages to be captured during pytest runs"""
    logging.getLogger().setLevel(logging.DEBUG)
    logging.captureWarnings(True)


@pytest.fixture
def app_config() -> models.BaseServiceConfig:
    return models.BaseServiceConfig(
        name='test_app',
        host='0.0.0.0',
        port=1234,
        debug=False,
        mqtt_protocol='mqtt',
        mqtt_host='eventbus',
        mqtt_port=1883,
        mqtt_path='/eventbus',
        history_topic='/brewcast/history',
        state_topic='/brewcast/state',
    )


@pytest.fixture
def sys_args(app_config: models.BaseServiceConfig) -> list:
    return [str(v) for v in [
        'app_name',
        '--name', app_config.name,
        '--host', app_config.host,
        '--port', app_config.port,
        '--mqtt-protocol', app_config.mqtt_protocol,
        '--mqtt-host', app_config.mqtt_host,
        '--mqtt-port', app_config.mqtt_port,
        '--mqtt-path', app_config.mqtt_path,
        '--history-topic', app_config.history_topic,
        '--state-topic', app_config.state_topic,
    ]]


@pytest.fixture
def app(app_config):
    app = service.create_app(app_config)
    return app


@pytest.fixture
async def app_setup(app):
    pass


@pytest.fixture
async def client(app, app_setup, aiohttp_client, aiohttp_server):
    """Allows patching the app or aiohttp_client before yielding it.

    Any tests wishing to add custom behavior to app can override the fixture
    """
    test_server: test_utils.TestServer = await aiohttp_server(app)
    test_client: test_utils.TestClient = await aiohttp_client(test_server)
    return test_client
