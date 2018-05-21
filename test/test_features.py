"""
Tests brewblox_service.features
"""

from asynctest import CoroutineMock
from brewblox_service import features

import pytest


class DummyFeature(features.ServiceFeature):
    def __init__(self, app, name: str=None):
        super().__init__(app)
        self.name = name

    async def startup(self, app):
        pass

    async def shutdown(self, app):
        pass


class OtherDummyFeature(features.ServiceFeature):
    async def startup(self, app):
        pass

    async def shutdown(self, app):
        pass


class DeprecatedFeature(features.ServiceFeature):

    def __init__(self, app):
        self.start = CoroutineMock()
        self.close = CoroutineMock()
        super().__init__(app)


def test_add(app):
    features.add(app, DummyFeature(app))
    assert app[features.FEATURES_KEY][DummyFeature]

    with pytest.raises(KeyError):
        features.add(app, DummyFeature(app))

    features.add(app, DummyFeature(app, 'galahad'), 'featy')
    assert app[features.FEATURES_KEY]['featy'].name == 'galahad'

    with pytest.raises(KeyError):
        features.add(app, DummyFeature(app, 'bedevere'), 'featy')

    features.add(app, DummyFeature(app, 'tim'), 'featy', exist_ok=True)
    assert app[features.FEATURES_KEY]['featy'].name == 'galahad'


def test_get(app):
    features.add(app, DummyFeature(app, 'dummy'))
    features.add(app, DummyFeature(app, 'jimmy'), 'jimmy')
    features.add(app, OtherDummyFeature(app), 'slagathor')

    assert features.get(app, DummyFeature).name == 'dummy'
    assert features.get(app, name='jimmy').name == 'jimmy'
    assert features.get(app, DummyFeature, name='jimmy').name == 'jimmy'

    with pytest.raises(KeyError):
        features.get(app, name='holy grail')

    with pytest.raises(AssertionError):
        features.get(app)

    # slagathor exists, but it's not a DummyFeature
    with pytest.raises(AssertionError):
        features.get(app, DummyFeature, 'slagathor')


async def test_name_deprecation(mocker, app, loop):
    warn_spy = mocker.spy(features.warnings, 'warn')

    debby = DeprecatedFeature(app)
    assert warn_spy.call_count == 1

    await debby.startup(app)
    debby.start.assert_called_once_with(app)

    await debby.shutdown(app)
    debby.close.assert_called_once_with(app)


async def test_lazy_feature(app, loop):
    # Does not implement any meaningful functions
    lazy = features.ServiceFeature(app)

    await lazy.startup(app)
    await lazy.shutdown(app)
