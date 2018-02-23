"""
Tests functionality offered by brewblox_service.events
"""

import pytest
from brewblox_service import events

TESTED = events.__name__


@pytest.fixture
async def app(app):
    """App with events enabled"""
    events.setup(app)
    return app


async def test_setup(app, client):
    pass
