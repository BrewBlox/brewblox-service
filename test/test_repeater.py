"""
Tests brewblox_service.repeater
"""

import asyncio
from unittest.mock import Mock

import pytest

from brewblox_service import features, repeater, scheduler

TESTED = repeater.__name__


class RepeaterDummy(repeater.RepeaterFeature):

    def __init__(self, app):
        self.prepare_mock = Mock()
        self.run_mock = Mock()
        self.interval = 0.01
        super().__init__(app)

    async def prepare(self):
        self.prepare_mock()

    async def run(self):
        await asyncio.sleep(self.interval)
        self.run_mock()


class ResumeDummy(RepeaterDummy):

    async def run(self):
        await asyncio.sleep(self.interval)
        self.run_mock()
        if self.run_mock.call_count == 1:
            raise RuntimeError()


@pytest.fixture
async def app(app):
    scheduler.setup(app)

    dummy = RepeaterDummy(app)
    features.add(app, dummy, 'dummy')

    prep_cancel = RepeaterDummy(app)
    prep_cancel.prepare_mock.side_effect = repeater.RepeaterCancelled
    features.add(app, prep_cancel, 'prep_cancel')

    prep_error = RepeaterDummy(app)
    prep_error.prepare_mock.side_effect = RuntimeError
    features.add(app, prep_error, 'prep_error')

    run_cancel = RepeaterDummy(app)
    run_cancel.run_mock.side_effect = repeater.RepeaterCancelled
    features.add(app, run_cancel, 'run_cancel')

    run_error = RepeaterDummy(app)
    run_error.run_mock.side_effect = RuntimeError
    features.add(app, run_error, 'run_error')

    run_resume = ResumeDummy(app)
    features.add(app, run_resume, 'run_resume')

    return app


async def test_dummies(app, client):
    dummy = features.get(app, key='dummy')
    prep_cancel = features.get(app, key='prep_cancel')
    prep_error = features.get(app, key='prep_error')
    run_cancel = features.get(app, key='run_cancel')
    run_error = features.get(app, key='run_error')
    run_resume = features.get(app, key='run_resume')

    await asyncio.sleep(0.1)

    assert dummy.active
    assert dummy.prepare_mock.call_count == 1
    assert dummy.run_mock.call_count > 1

    assert not prep_cancel.active
    assert prep_cancel.prepare_mock.call_count == 1
    assert prep_cancel.run_mock.call_count == 0

    assert not prep_error.active
    assert prep_error.prepare_mock.call_count == 1
    assert prep_error.run_mock.call_count == 0

    assert not run_cancel.active
    assert run_cancel.prepare_mock.call_count == 1
    assert run_cancel.run_mock.call_count == 1

    assert run_error.active
    assert run_error.prepare_mock.call_count == 1
    assert run_error.run_mock.call_count > 1

    assert run_resume.active
    assert run_resume.prepare_mock.call_count == 1
    assert run_resume.run_mock.call_count > 1
