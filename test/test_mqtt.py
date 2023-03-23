"""
Tests brewblox_service.mqtt
"""

import asyncio
import json
from subprocess import PIPE, check_call, check_output
from unittest.mock import AsyncMock, Mock, call

import pytest

from brewblox_service import mqtt, scheduler, testing

TESTED = mqtt.__name__


@pytest.fixture(scope='module')
def broker():
    mqtt_port = testing.find_free_port()
    check_call('docker stop mqtt-test-broker || true', shell=True)
    check_call('docker run -d --rm '
               '--name mqtt-test-broker '
               f'-p {mqtt_port}:1883 '
               'brewblox/mosquitto:develop',
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
        raise
    finally:
        print(check_output('docker logs -t mqtt-test-broker', shell=True))


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
    assert mqtt.decoded(None) is None


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


async def test_invalid(app, client, mocker):
    handler = mqtt.EventHandler(app, port=testing.find_free_port())
    await handler.shutdown(app)
    await handler.startup(app)

    with pytest.raises(RuntimeError):
        handler.set_client_will('brewcast/nope', None)

    with pytest.raises(ConnectionError):
        await handler.publish('test', '')

    # Mute error
    await handler.publish('test', '', err=False)


async def test_publish(app, client, connected):
    await mqtt.publish(app, 'brewcast/state/test', json.dumps({'testing': 123}))


class CallbackRecorder:

    def __init__(self) -> None:
        self.mock = Mock()
        self.expected = list()
        self.evt: asyncio.Event = None

    async def cb(self, topic, message):
        if not self.evt:
            self.evt = asyncio.Event()
        self.mock(topic, message)
        if self.mock.call_count >= len(self.expected):
            self.evt.set()


async def test_listen(app, client, connected, manual_handler):
    # Set listeners with varying wildcards
    # Errors in the callback should not interrupt
    cb1 = AsyncMock(side_effect=RuntimeError)
    await mqtt.listen(app, 'brewcast/#', cb1)
    cb2 = AsyncMock()
    await mqtt.listen(app, 'brewcast/state/+', cb2)
    cb3 = AsyncMock()
    await mqtt.listen(app, 'brewcast/state/test', cb3)
    cb4 = AsyncMock()
    await mqtt.listen(app, 'flapjacks', cb4)

    # Subscribe to a catch-all wildcard
    await mqtt.subscribe(app, 'brewcast/#')

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
    await mqtt.publish(app, 'pink/flamingos', 1)
    await mqtt.publish(app, 'brewcast/state/test', '2')
    await mqtt.publish(app, 'brewcast/empty', None)
    meaning = json.dumps({'meaning_of_life': True})
    await manual_handler.publish('brewcast/other', meaning)
    await mqtt.publish(app, 'brewcast/state/other', 3)
    manual_handler.client.publish('brewcast/bracket', '{')

    async def checker():
        while (cb1.await_count < 5
               or cb2.await_count < 2
               or cb3.await_count < 1
               or cbh1.await_count < 3):
            await asyncio.sleep(0.1)

    await asyncio.wait_for(checker(), 10)

    cb1.assert_has_awaits([
        call('brewcast/state/test', '2'),
        call('brewcast/empty', ''),
        call('brewcast/other', meaning),
        call('brewcast/state/other', '3'),
        call('brewcast/bracket', '{'),
    ], any_order=True)

    cb2.assert_has_awaits([
        call('brewcast/state/test', '2'),
        call('brewcast/state/other', '3'),
    ], any_order=True)

    cb3.assert_has_awaits([
        call('brewcast/state/test', '2'),
    ], any_order=True)

    cb4.assert_not_awaited()
    cb5.assert_not_awaited()

    cbh1.assert_has_awaits([
        call('brewcast/state/test', '2'),
        call('brewcast/other', meaning),
        call('brewcast/state/other', '3'),
        call('brewcast/bracket', '{'),
    ], any_order=True)

    cbh2.assert_not_awaited()
