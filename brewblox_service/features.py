"""
Registers and gets features added to Aiohttp by brewblox services.
"""

from abc import ABC, abstractmethod
from typing import Type

from aiohttp import web

FEATURES_KEY = '#features'


def add(app: web.Application,
        feature: 'ServiceFeature',
        name: str=None,
        exist_ok: bool=False):
    """
    Adds a new feature to the app.

    Features can either be registered as the default feature for the class,
    or be given an explicit name.

    If exist_ok is truthy, this function will do nothing if the request feature already exists.
    Otherwise it will raise an exception.
    """
    if FEATURES_KEY not in app:
        app[FEATURES_KEY] = dict()

    assert isinstance(feature, ServiceFeature), 'Can only add service features'
    name = name or type(feature)

    if name in app[FEATURES_KEY]:
        if exist_ok:
            return
        else:
            raise KeyError(f'Feature "{name}" already registered')

    app[FEATURES_KEY][name] = feature


def get(app: web.Application, feature_type: Type['ServiceFeature']=None, name: str=None):
    """
    Finds declared feature.
    Identification is done based on feature type and name.
    """
    name = name or feature_type
    assert name, 'No feature identifier provided'

    found = app.get(FEATURES_KEY, {}).get(name)

    if not found:
        raise KeyError(f'No feature found for "{name}"')

    assert not feature_type or isinstance(found, feature_type), f'Found {found} did not match type "{feature_type}"'

    return found


class ServiceFeature(ABC):

    def __init__(self, app: web.Application=None):
        if app:
            app.on_startup.append(self.start)
            app.on_cleanup.append(self.close)

    @abstractmethod
    async def start(self, app: web.Application):
        pass  # pragma: no cover

    @abstractmethod
    async def close(self, app: web.Application):
        pass  # pragma: no cover
