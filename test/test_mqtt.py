"""
Tests brewblox_service.mqtt
"""

import asyncio
import json
from subprocess import check_output
from unittest.mock import AsyncMock, Mock, call

import pytest

from brewblox_service import features, models, mqtt, scheduler, testing

TESTED = mqtt.__name__


@pytest.fixture(scope='module')
def broker():
    with testing.mqtt_broker() as ports:
        yield ports


@pytest.fixture
async def app_setup(app, mocker, broker):
    mocker.patch(TESTED + '.RECONNECT_INTERVAL_S', 0.001)

    config: models.ServiceConfig = app['config']
    config.mqtt_host = '0.0.0.0'
    config.mqtt_protocol = 'mqtt'
    config.mqtt_port = broker['mqtt']

    scheduler.setup(app)
    mqtt.setup(app, autostart=False)
    mqtt.set_client_will(app, 'brewcast/rip', None)

    features.add(app,
                 mqtt.EventHandler(app,
                                   protocol='ws',
                                   port=broker['ws'],
                                   autostart=False),
                 key='secondary')


async def wait_ready(handler: mqtt.EventHandler):
    await asyncio.wait_for(handler.ready.wait(), timeout=5)


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


async def test_create_mqtts(app, client, mocker):
    handler = mqtt.EventHandler(app, protocol='mqtts', autostart=False)
    assert handler.config.transport == 'tcp'

    mqtt._make_client(handler.config)


async def test_disconnected(app, client, mocker):
    handler = mqtt.fget(app)

    with pytest.raises(RuntimeError):
        handler.set_client_will('brewcast/nope', None)

    with pytest.raises(ConnectionError):
        await handler.publish('test', '')

    # Mute error
    await handler.publish('test', '', err=False)


async def test_publish(app, client):
    handler = mqtt.fget(app)
    await handler.start()
    await wait_ready(handler)
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


async def test_listen(app, client):
    handler = mqtt.fget(app)
    secondary = features.get(app, mqtt.EventHandler, 'secondary')

    await handler.start()
    await wait_ready(handler)

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
    await secondary.subscribe('#')

    # listen before connect
    cbh1 = AsyncMock()
    await secondary.listen('brewcast/#', cbh1)

    # listen/unlisten before connect
    cbh2 = AsyncMock()
    await secondary.listen('pink/#', cbh2)
    await secondary.unlisten('pink/#', cbh2)

    # subscribe/unsubscribe before connect
    await secondary.subscribe('pink/#')
    await secondary.unsubscribe('pink/#')

    # Start secondary handler
    await secondary.start()
    await wait_ready(secondary)

    # Publish a set of messages, with varying topics
    await mqtt.publish(app, 'pink/flamingos', 1)
    await mqtt.publish(app, 'brewcast/state/test', '2')
    await mqtt.publish(app, 'brewcast/empty', None)
    meaning = json.dumps({'meaning_of_life': True})
    await secondary.publish('brewcast/other', meaning)
    await mqtt.publish(app, 'brewcast/state/other', 3)
    await secondary.publish('brewcast/bracket', '{')

    async def checker():
        while (cb1.await_count < 5
               or cb2.await_count < 2
               or cb3.await_count < 1
               or cbh1.await_count < 3):
            await asyncio.sleep(0.1)

    await asyncio.wait_for(checker(), timeout=10)

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
