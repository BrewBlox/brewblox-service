"""
Tests brewblox_service.mqtt
"""
import asyncio
from subprocess import PIPE, check_call, check_output

import pytest
from mock import AsyncMock, call

from brewblox_service import mqtt, scheduler
from brewblox_service.testing import response

TESTED = mqtt.__name__


@pytest.fixture(scope='module')
def broker(find_free_port):
    mqtt_port = find_free_port()
    check_call('docker stop mqtt-test-broker || true', shell=True)
    check_call('docker run -d --rm '
               '--name mqtt-test-broker '
               f'-p {mqtt_port}:1883 '
               'eclipse-mosquitto',
               shell=True,
               stdout=PIPE)
    yield {'mqtt': mqtt_port}
    check_call('docker stop mqtt-test-broker', shell=True)


@pytest.fixture
def app(app, mocker, broker):
    mocker.patch(TESTED + '.RETRY_INTERVAL_S', 0.1)
    app['config']['mqtt_host'] = 'localhost'
    app['config']['mqtt_protocol'] = 'mqtt'
    app['config']['mqtt_port'] = broker['mqtt']

    scheduler.setup(app)
    mqtt.setup(app)

    return app


@pytest.fixture
async def connected(app, client, broker):
    await asyncio.wait_for(mqtt.handler(app)._connect_ev.wait(), timeout=2)


def test_config():
    cfg = mqtt.MQTTConfig('ws', 'eventbus', None, '/path')
    assert str(cfg) == 'ws://eventbus:80/path'

    cfg = mqtt.MQTTConfig('mqtts', 'localhost', None, '/wunderbar')
    assert str(cfg) == 'mqtts://localhost:8883'

    with pytest.raises(ValueError):
        # Invalid protocol
        mqtt.MQTTConfig('magic', 'eventbus', None, '/path')


def test_decoded():
    assert mqtt.decoded(b'testface') == 'testface'
    assert mqtt.decoded('testface') == 'testface'


async def test_broker(broker):
    assert 'mqtt-test-broker' in check_output('docker ps --format {{.Names}}', shell=True).decode()


async def test_create_client(app, client, mocker):
    m_client = mocker.patch(TESTED + '.aiomqtt.Client')
    cfg = mqtt.MQTTConfig('mqtts', 'localhost', None, '/wunderbar')
    c = mqtt.EventHandler.create_client(cfg)
    assert c is m_client.return_value
    c.tls_set.assert_called_once()


async def test_invalid(app, client, mocker, find_free_port):
    mocker.patch(TESTED + '.RETRY_INTERVAL_S', 0.001)
    handler = mqtt.EventHandler(app, port=find_free_port())
    await handler.startup(app)
    await asyncio.sleep(0.1)
    assert handler.active
    await handler.shutdown(app)

    with pytest.raises(ConnectionRefusedError):
        await handler.run()

    with pytest.raises(ConnectionError):
        await handler.publish('test', {})

    # Mute error
    await handler.publish('test', {}, err=False)


async def test_publish(app, client, connected):
    await mqtt.publish(app, 'brewcast/state/test', {'testing': 123})


async def test_listen(app, client, connected):
    # Set listeners with varying wildcards
    cb1 = AsyncMock()
    await mqtt.listen(app, 'brewcast/#', cb1)
    cb2 = AsyncMock()
    await mqtt.listen(app, 'brewcast/state/+', cb2)
    cb3 = AsyncMock()
    await mqtt.listen(app, 'brewcast/state/test', cb3)
    cb4 = AsyncMock()
    await mqtt.listen(app, 'flapjacks', cb4)

    # subscribe using the REST API
    await response(client.post('/_debug/subscribe',
                               json={'topic': 'brewcast/#'}))

    # subscribe/unsubscribe on connected client
    await mqtt.subscribe(app, 'pink/#')
    await mqtt.unsubscribe(app, 'pink/#')
    await mqtt.unsubscribe(app, 'pink/#')

    # listen/unlisten on connected client
    cb5 = AsyncMock()
    await mqtt.listen(app, 'brewcast/#', cb5)
    await mqtt.unlisten(app, 'brewcast/#', cb5)
    await mqtt.unlisten(app, 'brewcast/#', cb5)

    # must be started manually
    handler = mqtt.EventHandler(app)

    # subscribe before connect, and before listen
    await handler.subscribe('#')

    # listen before connect
    cbh1 = AsyncMock()
    await handler.listen('brewcast/#', cbh1)

    # listen/unlisten before connect
    cbh2 = AsyncMock()
    await handler.listen('pink/#', cbh2)
    await handler.unlisten('pink/#', cbh2)

    # subscribe/unsubscribe before connect
    await handler.subscribe('pink/#')
    await handler.unsubscribe('pink/#')

    # Start manually controlled handler
    # The default one is already connected (see: 'connected' fixture)
    await handler.startup(app)
    await asyncio.wait_for(handler._connect_ev.wait(), timeout=2)

    # Publish a set of messages, with varying topics
    await mqtt.publish(app, 'pink/flamingos', {})
    await mqtt.publish(app, 'brewcast/state/test', {})
    await handler.publish('brewcast/other', {'meaning_of_life': True})
    await response(client.post('/_debug/publish',
                               json={
                                   'topic': 'brewcast/state/other',
                                   'message': {},
                               }))

    await asyncio.sleep(1)

    cb1.assert_has_awaits([
        call('brewcast/state/test', {}),
        call('brewcast/other', {'meaning_of_life': True}),
        call('brewcast/state/other', {}),
    ], any_order=True)

    cb2.assert_has_awaits([
        call('brewcast/state/test', {}),
        call('brewcast/state/other', {}),
    ], any_order=True)

    cb3.assert_has_awaits([
        call('brewcast/state/test', {}),
    ], any_order=True)

    cb4.assert_not_awaited()
    cb5.assert_not_awaited()

    cbh1.assert_has_awaits([
        call('brewcast/state/test', {}),
        call('brewcast/other', {'meaning_of_life': True}),
        call('brewcast/state/other', {}),
    ], any_order=True)

    cbh2.assert_not_awaited()
