"""
Tests functionality offered by brewblox_service.events
"""

import asyncio
import json
from datetime import timedelta
from unittest.mock import AsyncMock, Mock, call

import aioamqp
import pytest

from brewblox_service import events, scheduler
from brewblox_service.testing import response

TESTED = events.__name__


@pytest.fixture
def m_channel():
    m = Mock()
    m.exchange_declare = AsyncMock()
    m.queue_declare = AsyncMock(return_value={'queue': 'queue_name'})
    m.queue_bind = AsyncMock()
    m.basic_consume = AsyncMock()
    m.basic_publish = AsyncMock()
    m.basic_client_ack = AsyncMock()
    return m


@pytest.fixture
def m_protocol(m_channel):
    m = Mock()
    m.channel = AsyncMock(return_value=m_channel)
    m.ensure_open = AsyncMock()
    m.close = AsyncMock()
    return m


@pytest.fixture
def m_transport():
    return Mock()


@pytest.fixture
def mocked_connect(mocker, m_protocol, m_transport):
    # connect()
    conn_mock_func = AsyncMock(spec=aioamqp.connect)
    conn_mock_func.return_value = (m_transport, m_protocol)

    mocker.patch.object(events.aioamqp, 'connect', conn_mock_func)

    return conn_mock_func


@pytest.fixture
async def app(app, mocker, loop, mocked_connect):
    """App with events enabled"""
    scheduler.setup(app)
    events.setup(app)
    mocker.patch(TESTED + '.RECONNECT_INTERVAL', timedelta(microseconds=100))
    return app


async def test_setup(app, client):
    assert events.get_listener(app)
    assert events.get_publisher(app)


async def test_subscribe_callbacks(app, client, mocker, m_channel):
    cb = Mock()
    content = dict(key='var')

    body = json.dumps(content)
    envelope_mock = Mock()
    envelope_mock.routing_key = 'message_key'
    properties_mock = Mock()

    sub = events.get_listener(app).subscribe(
        'brewblox', 'router', on_message=cb)

    await sub._relay(m_channel, body, envelope_mock, properties_mock)
    assert m_channel.basic_client_ack.call_count == 1
    cb.assert_called_once_with(sub, 'message_key', content)

    cb2 = Mock()
    sub.on_message = cb2

    await sub._relay(m_channel, body, envelope_mock, properties_mock)
    cb2.assert_called_once_with(sub, 'message_key', content)
    assert m_channel.basic_client_ack.call_count == 2
    assert cb.call_count == 1

    # Shouldn't blow up
    cb2.side_effect = ValueError
    await sub._relay(m_channel, body, envelope_mock, properties_mock)
    assert m_channel.basic_client_ack.call_count == 3

    # Should be tolerated
    sub.on_message = None
    await sub._relay(m_channel, body, envelope_mock, properties_mock)
    assert m_channel.basic_client_ack.call_count == 4


async def test_offline_listener(app, mocker):
    # We're not importing the client fixture, so the app is not running
    # Expected behaviour is for the listener to add functions to the app hooks
    listener = events.EventListener(app)

    # Subscriptions will not be declared yet - they're waiting for startup
    listener.subscribe('exchange', 'routing')
    assert listener._pending.qsize() == 1
    assert not listener.active


async def test_deferred_subscription(app, client):
    # Tests whether subscriptions made before startup are correctly initialized
    listener = events.EventListener(app)
    assert not listener.active
    listener.subscribe('exchange', 'route')
    await listener.prepare()
    assert listener._has_pending.is_set()


async def test_online_listener(app, client, mocker):
    listener = events.get_listener(app)
    events.subscribe(app, 'exchange', 'routing')

    pending_subs = listener._pending.qsize()
    events.subscribe(app, 'exchange', 'routing')
    # We haven't yielded, so the subscription can't have been processed yet
    assert listener._pending.qsize() == pending_subs + 1

    # Safe for repeated calls
    await listener.shutdown(app)
    await listener.shutdown(app)


async def test_offline_publisher(app):
    publisher = events.EventPublisher(app)
    await publisher.startup(app)
    await publisher.publish('exchange', 'key', message=dict(key='val'))


async def test_online_publisher(app, client, mocker):
    publisher = events.EventPublisher(app)
    await publisher.startup(app)

    await publisher.publish('exchange', 'key', message=dict(key='val'))
    await publisher.publish('exchange', 'key', message=dict(key='val'))


async def test_publish_endpoint(app, client, mocker, m_channel):
    # standard ok
    await response(client.post('/_debug/publish', json=dict(
        exchange='exchange',
        routing='first',
        message=dict(key='val')
    )))

    # string messages supported
    await response(client.post('/_debug/publish', json=dict(
        exchange='exchange',
        routing='second',
        message='message'
    )))

    mocker.patch.object(events.get_publisher(app),
                        '_ensure_channel',
                        AsyncMock(side_effect=RuntimeError))

    await response(client.post('/_debug/publish', json=dict(
        exchange='exchange',
        routing='first',
        message=dict(key='val')
    )), 500)

    msg1 = json.dumps({'key': 'val'}).encode()
    msg2 = json.dumps('message').encode()

    m_channel.basic_publish.assert_has_calls([
        call(payload=msg1, exchange_name='exchange', routing_key='first'),
        call(payload=msg2, exchange_name='exchange', routing_key='second'),
    ])


async def test_subscribe_endpoint(app, client, m_channel):
    await response(client.post('/_debug/subscribe', json=dict(
        exchange='exchange',
        routing='routing.key'
    )))

    await asyncio.sleep(0.01)

    m_channel.queue_bind.assert_awaited_once_with(
        queue_name='queue_name',
        exchange_name='exchange',
        routing_key='routing.key'
    )


async def test_listener_exceptions(app, client, m_protocol, m_channel, m_transport, mocked_connect):
    listener = events.get_listener(app)

    m_channel.basic_consume.side_effect = ConnectionRefusedError
    listener.subscribe('exchange', 'routing')

    # Let listener attempt to declare the new subscription a few times
    # In real scenarios we'd expect ensure_open() to also start raising exceptions
    await asyncio.sleep(0.01)
    m_protocol.ensure_open.side_effect = aioamqp.AmqpClosedConnection
    await asyncio.sleep(0.01)

    # Retrieved subscription, errored on basic_consume(), and put subscription back
    assert m_channel.basic_consume.call_count >= 1
    assert listener._pending.qsize() == 1
    assert not listener._task.done()

    # Error recovery
    m_protocol.ensure_open.side_effect = RuntimeError
    await asyncio.sleep(0.01)
    assert not listener._task.done()

    # Should be closed every time it was opened
    await listener.shutdown(app)
    assert m_protocol.close.call_count == mocked_connect.call_count
    assert m_transport.close.call_count == mocked_connect.call_count


async def test_listener_periodic_check(mocker, app, client, m_protocol):
    # No subscriptions were made - not listening
    await asyncio.sleep(0.1)
    assert m_protocol.ensure_open.call_count == 0

    listener = events.get_listener(app)

    # Should be listening now, an periodically calling ensure_open()
    listener.subscribe('exchange', 'routing')
    await asyncio.sleep(0.1)
    assert m_protocol.ensure_open.call_count > 0


async def test_publisher_exceptions(app, client, m_protocol):
    m_protocol.ensure_open.side_effect = aioamqp.AmqpClosedConnection

    with pytest.raises(aioamqp.AmqpClosedConnection):
        await events.get_publisher(app).publish('exchange', 'routing', 'message')
