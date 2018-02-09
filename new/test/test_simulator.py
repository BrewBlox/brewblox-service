"""
Tests functionality offered by brewblox_service.plugins.simulator
"""

from brewblox_service import plugger
import pytest


@pytest.fixture
def plugged(app):
    plugger.init_app(app)
    return app


def test_config(client, plugged):
    res = client.get('/simulator/config')
    assert res.status_code == 200
    assert res.json == {}

    # no args supplied
    assert client.post('/simulator/config').status_code == 500

    config = {
        '_id': 1,
        'enabled': True,
        'nested': {
            'key': 'val'
        },
        'array': [
            1, 2, 3
        ]
    }

    assert client.post('/simulator/config', json=config).status_code == 200

    # now retrieve
    res = client.get('/simulator/config')
    assert res.status_code == 200
    assert res.json == config
