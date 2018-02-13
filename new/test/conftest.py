"""
Master file for pytest fixtures.
Any fixtures declared here are available to all test functions in this directory.
"""

import json
import logging
import os

import pytest

from brewblox_service import rest


@pytest.fixture(scope='session', autouse=True)
def log_enabled():
    """Sets log level to DEBUG for all test functions.
    Allows all logged messages to be captured during pytest runs"""
    logging.getLogger().setLevel(logging.DEBUG)


@pytest.fixture
def app_config() -> dict:
    return {
        'name': 'test_app',
        'prefix': '',
        'plugin_dir': 'plugins',
    }


@pytest.fixture
def app(app_config):
    app = rest.create_app(app_config)
    # When we're testing, root path is one higher than it should be
    app.root_path = os.path.join(app.root_path, 'brewblox_service')
    # For the plugin mechanism, we need a valid app name
    app.name = 'brewblox_service'
    return app


@pytest.yield_fixture
def client(client):
    """Monkeypatch the Pytest-flask client to allow simple json post calls"""

    def jsonpost(*args, **kwargs):
        if 'json' in kwargs:
            kwargs['data'] = json.dumps(kwargs.pop('json'))
            kwargs['content_type'] = 'application/json'
        return client._post(*args, **kwargs)

    client._post = client.post
    client.post = jsonpost
    yield client
