"""
Tests functionality offered by brewblox_service.events
"""

import json
from unittest.mock import Mock, call

import aio_pika
import pytest
from asynctest import Mock as AsyncMock
from asynctest import CoroutineMock

from brewblox_service import events

TESTED = events.__name__


def set_connect_func(mocker, closed: bool):

    async def mocked_connect_robust(loop=None):
        conn_mock = AsyncMock(spec=aio_pika.robust_connection.RobustConnection)
        conn_mock.loop = loop
        conn_mock.is_closed = closed

        chan_mock = CoroutineMock()
        exchange_mock = CoroutineMock()
        queue_mock = CoroutineMock()

        queue_mock.bind = CoroutineMock()
        queue_mock.consume = CoroutineMock()

        exchange_mock.publish = CoroutineMock()

        chan_mock.declare_exchange = CoroutineMock(return_value=exchange_mock)
        chan_mock.declare_queue = CoroutineMock(return_value=queue_mock)

        conn_mock.close = CoroutineMock()
        conn_mock.channel = CoroutineMock(return_value=chan_mock)

        return conn_mock

    mocker.patch.object(events.aio_pika, 'connect_robust',
                        mocked_connect_robust)


@pytest.fixture
async def app(app, mocker, loop):
    """App with events enabled"""
    set_connect_func(mocker, closed=False)

    events.setup(app)
    return app


async def test_setup(app, client):
    assert events.get_listener(app)
    assert events.get_publisher(app)


async def test_subscribe_callbacks(app, client, mocker):
    cb = Mock()
    content = dict(key='var')
    pika_msg = Mock()
    pika_msg.routing_key = 'message_key'
    pika_msg.body = json.dumps(content)

    sub = events.get_listener(app).subscribe(
        'brewblox', 'router', on_message=cb)

    await sub._relay(pika_msg)
    cb.assert_called_once_with(sub, 'message_key', content)
    assert pika_msg.ack.call_count == 1

    cb2 = Mock()
    sub.on_message = cb2

    await sub._relay(pika_msg)
    cb2.assert_called_once_with(sub, 'message_key', content)
    assert cb.call_count == 1
    assert pika_msg.ack.call_count == 2

    # Shouldn't blow up
    cb2.side_effect = ValueError
    await sub._relay(pika_msg)

    # Should be tolerated
    sub.on_message = None
    await sub._relay(pika_msg)


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


async def test_closed_listener(app, client, mocker):
    set_connect_func(mocker, closed=True)

    listener = events.EventListener()
    await listener.start(app.loop)


async def test_disconnect_listener(app, client, mocker):
    listener = events.EventListener()
    await listener.start(app.loop)

    # Task should be started
    assert listener._task

    # Close connection. Task should gracefully exit now
    listener._connection.is_closed = True
    await listener._task


async def test_offline_publisher(app):
    publisher = events.EventPublisher(app)

    assert publisher._startup in app.on_startup
    assert publisher._cleanup in app.on_cleanup

    with pytest.raises(ConnectionRefusedError):
        await publisher.publish('exchange', 'key', message=dict(key='val'))


async def test_online_publisher(app, client, mocker):
    # Can't setup while running
    with pytest.raises(RuntimeError):
        events.EventPublisher(app)

    publisher = events.EventPublisher()
    await publisher.start(app.loop)

    await publisher.publish('exchange', 'key', message=dict(key='val'))
    await publisher.publish('exchange', 'key', message=dict(key='val'))


async def test_closed_publisher(app, client, mocker):
    set_connect_func(mocker, closed=True)

    publisher = events.EventPublisher()
    await publisher.start(app.loop)


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
    events.get_publisher(app)._connection.is_closed = True
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
