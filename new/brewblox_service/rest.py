from typing import Type

from flask import Flask
from flask.views import View
from flask_apispec import FlaskApiSpec
from flask_cors import CORS
from flask_marshmallow import Marshmallow


class Api():
    """REST API core class.

    Allows registering resources to endpoints.
    """

    def __init__(self, prefix: str=''):
        """Creates a new API object, where endpoints can be registered.

        Arguments:
            prefix (str): path to be prefixed to each registered endpoint.
        """
        self.specs = FlaskApiSpec()
        self.prefix = prefix.lstrip('/').rstrip('/')
        self._deferred_routes = []

    def register(self, path: str, resource: Type[View]):
        """Registers a new REST endpoint handler.

        Arguments:
            path (str): Relative endpoint path specifier.
            resource (View): Flask view that should handle requests to `path`.
        """
        self._deferred_routes.append(
            ('/{}/{}'.format(self.prefix, path.lstrip('/')),
             resource.as_view(name=resource.__name__.lower()))
        )

    def init_app(self, app: Type[Flask]):
        """Adds all registered endpoints to an app.

        Arguments:
            app (Flask): Flask application object.
        """
        for deferred in self._deferred_routes:
            app.add_url_rule(deferred[0], view_func=deferred[1])
            self.specs.register(deferred[1])
        self.specs.init_app(app)


def create_app(config: dict) -> Type[Flask]:
    app = Flask('brewblox_service')
    app.config.update(config)

    ma = Marshmallow(app)
    api = Api()

    # TODO(Bob) init all other app components

    CORS(app)
    api.init_app(app)
    ma.init_app(app)

    return app
