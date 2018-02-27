"""
Tests functionality offered by brewblox_service.simulator
"""

import pytest
from brewblox_service import simulator

TESTED = simulator.__name__


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
async def app(app):
    """App with simulator functions added"""
    simulator.setup(app)
    return app


async def test_config(client, sim_config):
    res = await client.get('/config')
    assert res.status == 200
    assert await res.json() == {}

    # no args supplied
    res = await client.post('/config')
    assert res.status == 500

    # actual config
    res = await client.post('/config', json=sim_config)
    assert res.status == 200

    # now retrieve
    res = await client.get('/config')
    assert res.status == 200
    assert await res.json() == sim_config


async def test_values(client, sim_config):
    res = await client.post('/config', json=sim_config)
    assert res.status == 200

    res = await client.get('/values')
    assert res.status == 200
    content = await res.json()
    assert len(content) == 2
    assert content[0]['identifier'] in ['1.2.3', '2.3.4']

    res = await client.get('/values/1.2.3')
    assert res.status == 200
    content = await res.json()
    assert content['identifier'] == '1.2.3'

    res = await client.get('/values/oilwell')
    assert res.status == 200
    assert await res.json() == dict()
