"""
Tests brewblox_service.features
"""

import pytest

from brewblox_service import features


class DummyFeature(features.ServiceFeature):
    def __init__(self, app, name: str = None, *args, **kwargs):
        super().__init__(app, *args, **kwargs)
        self.name = name

    def __bool__(self):
        # Falsey features should not raise exceptions in features.get()
        return False

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
    assert app[features.FEATURES_KEY][DummyFeature] is not None

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
    assert features.get(app, key='jimmy').name == 'jimmy'
    assert features.get(app, DummyFeature, key='jimmy').name == 'jimmy'
    assert hasattr(features.get(app, DummyFeature), 'before_shutdown')

    with pytest.raises(KeyError):
        features.get(app, key='holy grail')

    with pytest.raises(AssertionError):
        features.get(app)

    # slagathor exists, but it's not a DummyFeature
    with pytest.raises(AssertionError):
        features.get(app, DummyFeature, 'slagathor')


async def test_app_property(app, client):
    dummy = DummyFeature(app, 'dummy', startup=features.Startup.MANUAL)
    assert dummy.app == app

    with pytest.raises(AttributeError):
        dummy.app = app
