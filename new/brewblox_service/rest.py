import logging
from typing import Type

from flask import Flask, request
from flask.views import View
from flask_apispec import FlaskApiSpec
from flask_cors import CORS

LOGGER = logging.getLogger(__name__)


class Api():
    """REST API core class.

    Allows registering resources to endpoints.
    """

    def __init__(self, prefix: str=''):
        """Creates a new API object, where endpoints can be registered.

        Arguments:
            prefix (str): path to be prefixed to each registered endpoint.
        """
        self.prefix = prefix.lstrip('/').rstrip('/')
        self._deferred_routes = []

    def register(self, path: str, resource: Type[View]):
        """Registers a new REST endpoint handler.

        Arguments:
            path (str): Relative endpoint path specifier.
            resource (View): Flask view that should handle requests to `path`.
        """
        LOGGER.info('added route ("{}", {})'.format(path, resource))
        route = ('{}/{}'.format(self.prefix, path.lstrip('/')),
                 resource.as_view(name=resource.__name__.lower()))
        self._deferred_routes.append(route)

    def init_app(self, app: Type[Flask]):
        """Adds all registered endpoints to an app.

        Arguments:
            app (Flask): Flask application object.
        """
        specs = FlaskApiSpec()
        for deferred in self._deferred_routes:
            app.add_url_rule(deferred[0], view_func=deferred[1])
            specs.register(deferred[1])
        specs.init_app(app)


class Shutdown(View):
    methods = ['GET', 'POST']

    def shutdown_server(self):
        func = request.environ.get('werkzeug.server.shutdown')
        if func is None:
            raise RuntimeError('Not running with the Werkzeug Server')
        func()

    def dispatch_request(self):
        self.shutdown_server()
        return 'Shutting down...'


def create_app(config: dict) -> Type[Flask]:
    app = Flask(config['name'])
    app.config.update(config)

    api = Api()

    CORS(app)

    api.register('/shutdown', Shutdown)
    api.init_app(app)

    return app
