"""
Tests functionality offered by brewblox_service.plugins.simulator
"""

from brewblox_service import plugger
import pytest


@pytest.fixture
def sim_config():
    return [
        {
            'identifier': '1.2.3',
            'name': 'beer sensor 1',
            'type_id': 6,
            'settings': {
                'address': '0x2823456512',
                'offset': 0.12
            },
            'state': {
                'value': 20.0,
                'connect': False
            }
        },
        {
            'identifier': '2.3.4',
            'name': 'beer sensor 1',
            'type_id': 6,
            'settings': {
                'address': '0x2823456512',
                'offset': 0.12
            },
            'state': {
                'value': 20.0,
                'connect': True
            }
        }
    ]


@pytest.fixture
def plugged(app):
    plugger.init_app(app)
    return app


def test_config(client, plugged, sim_config):
    res = client.get('/config')
    assert res.status_code == 200
    assert res.json == {}

    # no args supplied
    assert client.post('/config').status_code == 500

    # actual config
    assert client.post('/config', json=sim_config).status_code == 200

    # now retrieve
    res = client.get('/config')
    assert res.status_code == 200
    assert res.json == sim_config


def test_values(client, plugged, sim_config):
    assert client.post('/config', json=sim_config).status_code == 200

    res = client.get('/values')
    assert res.status_code == 200
    assert len(res.json) == 2
    assert res.json[0]['identifier'] in ['1.2.3', '2.3.4']
    print(res.json)

    res = client.get('/values/1.2.3')
    assert res.status_code == 200
    assert res.json['identifier'] == '1.2.3'

    res = client.get('/values/oilwell')
    assert res.status_code == 200
    assert res.json == dict()
