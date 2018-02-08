"""
Master file for pytest fixtures.
Any fixtures declared here are available to all test functions in this directory.
"""

import logging

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
        'plugin_dir': 'plugins'
    }


@pytest.fixture
def app(app_config):
    app = rest.create_app(app_config)
    return app
