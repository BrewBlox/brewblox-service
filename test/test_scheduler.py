"""
Tests brewblox_service.scheduler
"""


import asyncio

import pytest

from brewblox_service import scheduler

TESTED = scheduler.__name__


@pytest.fixture
async def app_setup(app, mocker):
    mocker.patch(TESTED + '.CLEANUP_INTERVAL_S', 0.001)
    scheduler.setup(app)


async def test_create_cancel(app, client):

    async def do(ev):
        ev.set()
        return 'ok'

    ev = asyncio.Event()
    task = await scheduler.create(app, do(ev))
    await ev.wait()

    assert [
        await scheduler.cancel(app, task),
        await scheduler.cancel(app, task),
        await scheduler.cancel(app, task, False),
    ] == ['ok', 'ok', None]

    # Create and forget
    await scheduler.create(app, do(asyncio.Event()))

    # Cancelling None does not croak
    await scheduler.cancel(app, None)


async def test_cleanup(app, client):
    async def dummy():
        pass

    sched = scheduler.fget(app)
    start_count = len(sched._tasks)
    task = await scheduler.create(app, dummy())
    await asyncio.sleep(0.01)

    assert task.done()
    assert len(sched._tasks) == start_count
