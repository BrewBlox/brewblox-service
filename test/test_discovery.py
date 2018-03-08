"""
Tests brewblox_service.discovery
"""

import pytest
from brewblox_service import discovery
from aioresponses import aioresponses
from asynctest import CoroutineMock

TESTED = discovery.__name__


@pytest.fixture
async def app(app):
    """App with discovery enabled"""
    discovery.setup(app)
    return app


@pytest.fixture
def feature_data():
    return [dict(
        Address='hostey',
        ServiceAddress='hostex'
    )]


async def test_find_feature(app, client, feature_data):
    with aioresponses() as res:
        res.get('http://consul:8500/v1/catalog/service/fancy_feature', payload=feature_data)

        feature_addr = await discovery.find_feature(app, 'fancy_feature')
        assert feature_addr == dict(host='hostex')

        feature_data[0]['ServiceAddress'] = ''
        res.get('http://consul:8500/v1/catalog/service/fancy_feature', payload=feature_data)

        feature_addr = await discovery.find_feature(app, 'fancy_feature')
        assert feature_addr == dict(host='hostey')


async def test_feature_not_found(app, client):
    with aioresponses() as res:
        res.get('http://consul:8500/v1/catalog/service/fancy_feature', payload=[])

        feature_addr = await discovery.find_feature(app, 'fancy_feature')
        assert feature_addr == dict(host='localhost')


async def test_discovery_error(app, client):
    # Request will fail connection, regardless of test environment
    with aioresponses():
        feature_addr = await discovery.find_feature(app, 'fancy_feature')
        assert feature_addr == dict(host='localhost')


async def test_query_find(app, client, feature_data, mocker):
    find_mock = mocker.patch(TESTED + '.find_feature', CoroutineMock())
    find_mock.return_value = dict(host='hostex')

    query_res = await client.get('/_debug/discover/fancy_feature')

    assert query_res.status == 200
    assert (await query_res.json()) == dict(host='hostex')
    find_mock.assert_called_once_with(app, 'fancy_feature')
