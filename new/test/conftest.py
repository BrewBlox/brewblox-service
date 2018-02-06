"""
Master file for pytest fixtures.
Any fixtures declared here are available to all test functions in this directory.
"""

import pytest
from brewblox_service import __main__ as main


@pytest.fixture
def app():
    app = main.create_app({})
    return app
