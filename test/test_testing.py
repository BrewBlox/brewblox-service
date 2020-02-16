"""
Tests brewblox_service.testing
"""

import pytest

from brewblox_service import service, testing


@pytest.fixture
async def app(app, mocker):
    service.furnish(app)
    return app


async def test_response(app, client):
    await testing.response(client.get('/test_app/_service/status'))
    with pytest.raises(AssertionError):
        await testing.response(client.get('/test_app/_service/status'), 400)
