"""
Tests functionality offered by brewblox_service.events
"""

import asyncio
import json
from datetime import timedelta
from unittest.mock import Mock, call

import aioamqp
import pytest
from asynctest import CoroutineMock
from brewblox_service import events

TESTED = events.__name__


@pytest.fixture
def channel_mock():
    m = Mock()
    m.exchange_declare = CoroutineMock()
    m.queue_declare = CoroutineMock(return_value={'queue': 'queue_name'})
    m.queue_bind = CoroutineMock()
    m.basic_consume = CoroutineMock()
    m.basic_publish = CoroutineMock()
    return m


@pytest.fixture
def protocol_mock(channel_mock):
    m = Mock()
    m.channel = CoroutineMock(return_value=channel_mock)
    m.ensure_open = CoroutineMock()
    m.close = CoroutineMock()
    return m


@pytest.fixture
def transport_mock():
    return Mock()


@pytest.fixture
def mocked_connect(mocker, protocol_mock, transport_mock):
    # connect()
    conn_mock_func = CoroutineMock(spec=aioamqp.connect)
    conn_mock_func.return_value = (transport_mock, protocol_mock)

    mocker.patch.object(events.aioamqp, 'connect', conn_mock_func)

    return conn_mock_func


@pytest.fixture
async def app(app, mocker, loop, mocked_connect):
    """App with events enabled"""
    events.setup(app)
    mocker.patch(TESTED + '.PENDING_WAIT_TIMEOUT', timedelta(microseconds=10))
    mocker.patch(TESTED + '.RECONNECT_INTERVAL', timedelta(microseconds=10))
    return app


async def test_setup(app, client):
    assert events.EVENTBUS_HOST == 'eventbus'
    assert events.get_listener(app)
    assert events.get_publisher(app)


async def test_subscribe_callbacks(app, client, mocker):
    cb = Mock()
    content = dict(key='var')

    chan_mock = Mock()
    body = json.dumps(content)
    envelope_mock = Mock()
    envelope_mock.routing_key = 'message_key'
    properties_mock = Mock()

    sub = events.get_listener(app).subscribe(
        'brewblox', 'router', on_message=cb)

    await sub._relay(chan_mock, body, envelope_mock, properties_mock)
    cb.assert_called_once_with(sub, 'message_key', content)

    cb2 = Mock()
    sub.on_message = cb2

    await sub._relay(chan_mock, body, envelope_mock, properties_mock)
    cb2.assert_called_once_with(sub, 'message_key', content)
    assert cb.call_count == 1

    # Shouldn't blow up
    cb2.side_effect = ValueError
    await sub._relay(chan_mock, body, envelope_mock, properties_mock)

    # Should be tolerated
    sub.on_message = None
    await sub._relay(chan_mock, body, envelope_mock, properties_mock)


async def test_offline_listener(app, mocker):
    # We're not importing the client fixture, so the app is not running
    # Expected behaviour is for the listener to add functions to the app hooks
    listener = events.EventListener(app)

    assert listener._startup in app.on_startup
    assert listener._cleanup in app.on_cleanup

    # Subscriptions will not be declared yet - they're waiting for startup
    sub = listener.subscribe('exchange', 'routing')
    assert sub in listener._pending_pre_async

    # Can safely be called, but will be a no-op at this time
    await listener.close()


async def test_online_listener(app, client, mocker):
    # The client fixture has started running the app in the event loop
    # We'll need to start explicitly
    with pytest.raises(RuntimeError):
        events.EventListener(app)

    listener = events.EventListener()
    sub = listener.subscribe('exchange', 'routing')

    # No-op, listener is not yet started
    await listener.close()

    assert sub in listener._pending_pre_async
    await listener.start(app.loop)
    assert listener._pending_pre_async is None

    pending_subs = listener._pending.qsize()
    listener.subscribe('exchange', 'routing')
    # We haven't yielded, so the subscription can't have been processed yet
    assert listener._pending.qsize() == pending_subs + 1

    # Safe for repeated calls
    await listener.close()
    await listener.close()


async def test_offline_publisher(app):
    publisher = events.EventPublisher(app)

    assert publisher._startup in app.on_startup
    assert publisher._cleanup in app.on_cleanup

    # with pytest.raises(ConnectionRefusedError):
    await publisher.publish('exchange', 'key', message=dict(key='val'))


async def test_online_publisher(app, client, mocker):
    # Can't setup while running
    with pytest.raises(RuntimeError):
        events.EventPublisher(app)

    publisher = events.EventPublisher()
    await publisher.start(app.loop)

    await publisher.publish('exchange', 'key', message=dict(key='val'))
    await publisher.publish('exchange', 'key', message=dict(key='val'))


async def test_publish_endpoint(app, client, mocker):
    publish_spy = mocker.spy(events.get_publisher(app), 'publish')

    # standard ok
    assert (await client.post('/_debug/publish', json=dict(
        exchange='exchange',
        routing='first',
        message=dict(key='val')
    ))).status == 200

    # string messages supported
    assert (await client.post('/_debug/publish', json=dict(
        exchange='exchange',
        routing='second',
        message='message'
    ))).status == 200

    # return 500 on connection refused
    events.get_publisher(app)._ensure_channel = CoroutineMock(side_effect=ConnectionRefusedError)
    assert (await client.post('/_debug/publish', json=dict(
        exchange='exchange',
        routing='third',
        message='message'
    ))).status == 500

    publish_spy.assert_has_calls([
        call('exchange', 'first', dict(key='val')),
        call('exchange', 'second', 'message'),
        call('exchange', 'third', 'message'),
    ])


async def test_subscribe_endpoint(app, client, channel_mock):
    assert (await client.post('/_debug/subscribe', json=dict(
        exchange='exchange',
        routing='routing.key'
    ))).status == 200

    await asyncio.sleep(0.01)

    channel_mock.queue_bind.assert_called_once_with(
        queue_name='queue_name',
        exchange_name='exchange',
        routing_key='routing.key'
    )


async def test_listener_exceptions(app, client, protocol_mock, channel_mock, transport_mock, mocked_connect):
    listener = events.get_listener(app)

    channel_mock.basic_consume.side_effect = ConnectionRefusedError
    listener.subscribe('exchange', 'routing')

    # Let listener attempt to declare the new subscription a few times
    # In real scenarios we'd expect ensure_open() to also start raising exceptions
    await asyncio.sleep(0.01)
    protocol_mock.ensure_open.side_effect = aioamqp.AmqpClosedConnection
    await asyncio.sleep(0.01)

    # Retrieved subscription, errored on basic_consume(), and put subscription back
    assert channel_mock.basic_consume.call_count >= 1
    assert listener._pending.qsize() == 1
    assert not listener._task.done()

    # Recoverable error
    protocol_mock.ensure_open.side_effect = aioamqp.AmqpClosedConnection
    await asyncio.sleep(0.01)
    assert not listener._task.done()

    # Critical error
    protocol_mock.ensure_open.side_effect = RuntimeError
    await asyncio.sleep(0.01)
    assert listener._task.done()

    # Should be closed every time it was opened
    assert protocol_mock.close.call_count == mocked_connect.call_count
    assert transport_mock.close.call_count == mocked_connect.call_count


async def test_listener_periodic_check(mocker, app, client, loop, protocol_mock):
    # Check that the listener periodically called ensure_open to check
    start_count = protocol_mock.ensure_open.call_count
    await asyncio.sleep(0.1)
    assert protocol_mock.ensure_open.call_count > start_count


async def test_listener_close_error(app, client, loop, mocked_connect):
    mocked_connect.side_effect = ConnectionRefusedError
    listener = events.EventListener()
    await listener.start(loop)
    await asyncio.sleep(0.01)

    # ConnectionRefused is deemed recoverable
    assert not listener._task.done()

    # Closed after unrecoverable error, but application still alive
    mocked_connect.side_effect = RecursionError
    await asyncio.sleep(0.01)
    assert listener._task.done()


async def test_publisher_exceptions(app, client, protocol_mock):
    protocol_mock.ensure_open.side_effect = aioamqp.AmqpClosedConnection

    with pytest.raises(aioamqp.AmqpClosedConnection):
        await events.get_publisher(app).publish('exchange', 'routing', 'message')
