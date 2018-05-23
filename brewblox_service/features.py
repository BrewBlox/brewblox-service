"""
Registers and gets features added to Aiohttp by brewblox services.
"""

import warnings
from abc import ABC
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
    """Base class for long-lived Aiohttp handler classes.

    For classes with async functionality,
    the (synchronous) `__init__()` and `__del__()` functions may not be sufficient.
    Aiohttp offers comparable init/deinit hooks, but inside the context of a running event loop.

    ServiceFeature registers the `self.startup(self, app)` and `self.shutdown(self, app)` as lifecycle callbacks.
    They will be called by Aiohttp at the appropriate moment.
    By overriding these functions, subclasses can perform initialization/deinitialization that requires an event loop.

    Note: Aiohttp will not accept registration of new callbacks after it started running.
    Automatic lifecycle management can be disabled by passing a None value to `ServiceFeature.__init__(self, app)`.
    In this case, `startup()` and `shutdown()` will need to be called manually.

    Example class:

        import asyncio
        from aiohttp import web
        from brewblox_service import service
        from brewblox_service.features import ServiceFeature

        class MyFeature(ServiceFeature):

            def __init__(self, app: web.Application):
                super().__init__(app)
                self._task: asyncio.Task = None

            async def startup(self, app: web.Application):
                # Schedule a long-running background task
                self._task = app.loop.create_task(self._hello())

            async def shutdown(self, app: web.Application):
                # Orderly cancel the background task
                try:
                    self._task.cancel()
                    await self._task
                except Exception:
                    pass

            async def _hello(self):
                while True:
                    await asyncio.sleep(5)
                    print('still here!')

    Example use:

        app = service.create_app(default_name='example')

        greeter = MyFeature(app)

        service.furnish(app)
        service.run(app)
        # greeter.startup(app) is called now

        # Press Ctrl+C to quit
        # greeter.shutdown(app) will be called
    """

    def __init__(self, app: web.Application):
        if any([
            callable(getattr(self, 'start', None)),
            callable(getattr(self, 'close', None))
        ]):
            message = 'start(app) and close(app) functions are deprecated. Use startup(app) and shutdown(app) instead'
            warnings.warn(message)

        if app:
            app.on_startup.append(self.startup)
            app.on_cleanup.append(self.shutdown)

    async def startup(self, app: web.Application):
        """Lifecycle hook for initializing the feature in an async context.

        Subclasses are expected to override this function.

        If `app` in the ServiceFeature.__init__(app) call was not None,
        startup() will be called when Aiohttp starts running.
        """

        # Attempt to fall back on old function name
        if callable(getattr(self, 'start', None)):
            await self.start(app)

    async def shutdown(self, app: web.Application):
        """Lifecycle hook for shutting down the feature before the event loop is closed.

        Subclasses are expected to override this function.

        If `app` in the ServiceFeature.__init__(app) call was not None,
        shutdown() will be called when Aiohttp is closing, but before the event loop is closed.
        """

        # Attempt to fall back on old function name
        if callable(getattr(self, 'close', None)):
            await self.close(app)
