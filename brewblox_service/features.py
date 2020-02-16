"""
Registers and gets features added to Aiohttp by brewblox services.
"""

from abc import ABC, abstractmethod
from enum import Enum, auto
from functools import wraps
from typing import Any, Hashable, Optional, Type, Union

from aiohttp import web

from brewblox_service import brewblox_logger

FEATURES_KEY = '#features'

LOGGER = brewblox_logger(__name__)


def add(app: web.Application,
        feature: Any,
        key: Optional[Union[Hashable, Type[Any]]] = None,
        exist_ok: bool = False
        ):
    """
    Adds a new feature to the app.

    Features can either be registered as the default feature for the class,
    or be given an explicit name.

    Args:
        app (web.Application):
            The current Aiohttp application.

        feature (Any):
            The new feature that should be registered.
            It is recommended, but not required to use a `ServiceFeature`.

        key (Hashable, optional):
            The key under which the feature should be registered.
            Defaults to `type(feature)`.

        exist_ok (bool):
            If truthy, this function will do nothing if a feature was already registered for `key`.
            Otherwise, an exception is raised.

    """
    if FEATURES_KEY not in app:
        app[FEATURES_KEY] = dict()

    key = key or type(feature)

    if key in app[FEATURES_KEY]:
        if exist_ok:
            return
        else:
            raise KeyError(f'Feature "{key}" already registered')

    app[FEATURES_KEY][key] = feature


def get(app: web.Application,
        feature_type: Optional[Type[Any]] = None,
        key: Optional[Hashable] = None
        ) -> Any:
    """
    Finds declared feature.
    Identification is done based on feature type and key.

    Args:
        app (web.Application):
            The current Aiohttp application.

        feature_type (Type[Any]):
            The Python type of the desired feature.
            If specified, it will be checked against the found feature.

        key (Hashable):
            A specific identifier for the desired feature.
            Defaults to `feature_type`

    Returns:
        Any: The feature found for the combination of `feature_type` and `key`
    """
    actual: Union[Hashable, Type[Any], None] = key or feature_type

    if actual is None:
        raise AssertionError('No feature identifier provided')

    try:
        found = app[FEATURES_KEY][actual]
    except KeyError:
        raise KeyError(f'No feature found for "{actual}"')

    if feature_type and not isinstance(found, feature_type):
        raise AssertionError(f'Found {found} did not match type "{feature_type}"')

    return found


class Startup(Enum):
    MANAGED = auto()
    MANUAL = auto()
    AUTODETECT = auto()


class ServiceFeature(ABC):
    """Base class for long-lived Aiohttp handler classes.

    For classes with async functionality,
    the (synchronous) `__init__()` and `__del__()` functions may not be sufficient.
    Aiohttp offers comparable init/deinit hooks, but inside the context of a running event loop.

    ServiceFeature registers the `self.startup(self, app)`, `self.before_shutdown(app)`,
     and `self.shutdown(self, app)` as lifecycle callbacks.
    They will be called by Aiohttp at the appropriate moment.
    By overriding these functions, subclasses can perform initialization/deinitialization that requires an event loop.

    Note: Aiohttp will not accept registration of new callbacks after it started running.
    Startup management can be adjusted by using the `startup` argument in `ServiceFeature.__init__()`

    Example class:

        import asyncio
        import random
        from aiohttp import web
        from brewblox_service import scheduler, service
        from brewblox_service.features import ServiceFeature

        class MyFeature(ServiceFeature):

            def __init__(self, app: web.Application):
                super().__init__(app)
                self._task: asyncio.Task = None

            async def startup(self, app: web.Application):
                # Schedule a long-running background task
                self._task = await scheduler.create(app, self._hello())

            async def before_shutdown(self, app: web.Application):
                print('Any minute now...')

            async def shutdown(self, app: web.Application):
                # Orderly cancel the background task
                await scheduler.cancel(app, self._task)

            async def _hello(self):
                while True:
                    await asyncio.sleep(5)
                    print(random.choice([
                        'Hellooo',
                        'Searching',
                        'Sentry mode activated',
                        'Is anyone there?',
                        'Could you come over here?',
                    ]))

    Example use:

        app = service.create_app(default_name='example')

        scheduler.setup(app)
        greeter = MyFeature(app)

        service.furnish(app)
        service.run(app)
        # greeter.startup(app) is called now

        # Press Ctrl+C to quit
        # greeter.before_shutdown(app) will be called
        # greeter.shutdown(app) will be called
    """

    def __hook(self, func, evt):
        @wraps(func)
        async def decorator(app):
            LOGGER.debug(f'--> {evt} {self}')
            retv = await func(app)
            LOGGER.debug(f'<-- {evt} {self}')
            return retv
        return decorator

    def __init__(self, app: web.Application, startup=Startup.AUTODETECT):
        """
        ServiceFeature constructor.

        Args:
            app (web.Application):
                The Aiohttp application with which the feature should be associated.

            startup (Startup):
                How feature lifecycle management should be handled. Default is AUTODETECT.
                    MANAGED:    Feature always registers lifecycle hooks.
                                This will raise an exception when creating
                                the feature while the application is running.

                    MANUAL:     Feature will not register lifecycle hooks.
                                startup() and shutdown() must be called manually.

                    AUTODETECT: Feature will register lifecycle hooks only if app is not running.
                                Behaves like MANAGED before application start,
                                and like MANUAL after application start.

        """
        self.__active_app: web.Application = app

        if any([
            startup == Startup.MANAGED,
            startup == Startup.AUTODETECT and not app.frozen
        ]):
            app.on_startup.append(self.__hook(self.startup, 'startup'))
            app.on_shutdown.append(self.__hook(self.before_shutdown, 'before_shutdown'))
            app.on_cleanup.append(self.__hook(self.shutdown, 'shutdown'))

    def __str__(self):
        return f'<{type(self).__name__}>'

    @property
    def app(self) -> web.Application:
        """Currently active `web.Application`

        Returns:
            web.Application: The current app.
        """
        return self.__active_app

    @abstractmethod
    async def startup(self, app: web.Application):
        """Lifecycle hook for initializing the feature in an async context.

        Subclasses are expected to override this function.

        Depending on the `startup` argument in `__init__()`,
        `startup()` will be called when Aiohttp starts running.

        Args:
            app (web.Application):
                Current Aiohttp application.
        """

    async def before_shutdown(self, app: web.Application):
        """Lifecycle hook for preparing to shut down the feature.

        Subclasses may override this function, but it is not mandatory.

        Depending on the `startup` argument in `__init__()`,
        `before_shutdown()` will be called when Aiohttp is closing.

        Args:
            app (web.Application):
                Current Aiohttp application.
        """

    @abstractmethod
    async def shutdown(self, app: web.Application):
        """Lifecycle hook for shutting down the feature before the event loop is closed.

        Subclasses are expected to override this function.

        Depending on the `startup` argument in `__init__()`,
        `shutdown()` will be called when Aiohttp is closing.

        Args:
            app (web.Application):
                Current Aiohttp application.
        """
