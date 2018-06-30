"""
Tests brewblox_service.scheduler
"""


import asyncio

from brewblox_service import scheduler

import pytest

TESTED = scheduler.__name__


@pytest.fixture
def app(app, mocker):
    mocker.patch(TESTED + '.CLEANUP_INTERVAL_S', 0.001)

    scheduler.setup(app)
    return app


async def test_create_cancel(app, client):

    async def do(ev):
        ev.set()
        return 'ok'

    ev = asyncio.Event()
    task = await scheduler.create_task(app, do(ev))
    await ev.wait()

    assert [
        await scheduler.cancel_task(app, task),
        await scheduler.cancel_task(app, task),
        await scheduler.cancel_task(app, task, False),
    ] == ['ok', 'ok', None]

    # Create and forget
    await scheduler.create_task(app, do(asyncio.Event()))

    # Cancelling None does not croak
    await scheduler.cancel_task(app, None)
