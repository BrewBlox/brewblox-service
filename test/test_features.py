"""
Tests brewblox_service.features
"""

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


async def test_app_property(app, client):
    dummy = DummyFeature(None, 'dummy')
    assert dummy.app is None

    await dummy.startup(app)
    assert dummy.app == app

    await dummy.shutdown(app)
    assert dummy.app is None

    with pytest.raises(AttributeError):
        dummy.app = app
