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
               'brewblox/brewblox-mosquitto:develop',
               shell=True,
               stdout=PIPE)
    yield {'mqtt': mqtt_port}
    check_call('docker stop mqtt-test-broker', shell=True)


@pytest.fixture
def app(app, mocker, broker):
    app['config']['mqtt_host'] = '0.0.0.0'
    app['config']['mqtt_protocol'] = 'mqtt'
    app['config']['mqtt_port'] = broker['mqtt']

    scheduler.setup(app)
    mqtt.setup(app)
    mqtt.set_client_will(app, 'brewcast/rip', None)

    return app


@pytest.fixture
async def connected(app, client, broker):
    try:
        await asyncio.wait_for(mqtt.handler(app)._connect_ev.wait(), timeout=5)
    except asyncio.TimeoutError:
        print(check_output('docker ps', shell=True).decode())
        print(check_output('docker logs -t mqtt-test-broker', shell=True))
        raise


@pytest.fixture
async def manual_handler(app, client):
    handler = mqtt.EventHandler(app)
    yield handler
    await handler.shutdown(app)


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

    assert not cfg.client_will
    cfg.client_will = {'topic': 'brewcast/test'}

    c = mqtt.EventHandler.create_client(cfg)
    assert c is m_client.return_value
    c.tls_set.assert_called_once()
    c.will_set.assert_called_once()


async def test_invalid(app, client, mocker, find_free_port):
    handler = mqtt.EventHandler(app, port=find_free_port())
    await handler.shutdown(app)
    await handler.startup(app)

    with pytest.raises(RuntimeError):
        handler.set_client_will('brewcast/nope', None)

    with pytest.raises(ConnectionError):
        await handler.publish('test', {})

    # Mute error
    await handler.publish('test', {}, err=False)


async def test_publish(app, client, connected):
    await mqtt.publish(app, 'brewcast/state/test', {'testing': 123})


async def test_listen(app, client, connected, manual_handler):
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

    # subscribe before connect, and before listen
    await manual_handler.subscribe('#')

    # listen before connect
    cbh1 = AsyncMock()
    await manual_handler.listen('brewcast/#', cbh1)

    # listen/unlisten before connect
    cbh2 = AsyncMock()
    await manual_handler.listen('pink/#', cbh2)
    await manual_handler.unlisten('pink/#', cbh2)

    # subscribe/unsubscribe before connect
    await manual_handler.subscribe('pink/#')
    await manual_handler.unsubscribe('pink/#')

    # Start manually controlled handler
    # The default one is already connected (see: 'connected' fixture)
    await manual_handler.startup(app)
    await asyncio.wait_for(manual_handler._connect_ev.wait(), timeout=2)

    # Publish a set of messages, with varying topics
    await mqtt.publish(app, 'pink/flamingos', {})
    await mqtt.publish(app, 'brewcast/state/test', {})
    await mqtt.publish(app, 'brewcast/empty', None)
    await manual_handler.publish('brewcast/other', {'meaning_of_life': True})
    await response(client.post('/_debug/publish',
                               json={
                                   'topic': 'brewcast/state/other',
                                   'message': {},
                               }))

    manual_handler.client.publish('brewcast/invalid', '{')

    delay_count = 0
    while (cb1.await_count < 4
            or cb2.await_count < 2
           or cb3.await_count < 1
           or cbh1.await_count < 3):
        delay_count += 1
        if delay_count >= 10:
            break
        await asyncio.sleep(1)

    cb1.assert_has_awaits([
        call('brewcast/state/test', {}),
        call('brewcast/other', {'meaning_of_life': True}),
        call('brewcast/state/other', {}),
        call('brewcast/empty', None)
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
