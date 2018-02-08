"""
Master file for pytest fixtures.
Any fixtures declared here are available to all test functions in this directory.
"""

import pytest
from brewblox_service import rest


@pytest.fixture
def app_config() -> dict:
    return {
        'name': 'test_app'
    }


@pytest.fixture
def app(app_config):
    app = rest.create_app(app_config)
    return app
