"""
Tests brewblox_service.testing
"""

from unittest.mock import Mock

import pytest

from brewblox_service import service, testing


@pytest.fixture
def app(app, mocker):
    service.furnish(app)
    return app


async def test_response(app, client):
    await testing.response(client.get('/test_app/_service/status'))
    with pytest.raises(AssertionError):
        await testing.response(client.get('/test_app/_service/status'), 400)


def test_matching():
    obj = testing.matching(r'.art')
    assert obj == 'cart'
    assert obj == 'part'
    assert obj != 'car'
    assert obj != ''

    mock = Mock()
    mock('fart')
    mock.assert_called_with(obj)
