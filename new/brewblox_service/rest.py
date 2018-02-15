import logging
import re
from typing import Type

from flask import Flask, request, jsonify
from flask.views import View

LOGGER = logging.getLogger(__name__)


class Shutdown(View):
    methods = ['POST']

    def shutdown_server(self):
        func = request.environ.get('werkzeug.server.shutdown')
        if func is None:
            raise RuntimeError('Not running with the Werkzeug Server')
        func()

    def dispatch_request(self):
        self.shutdown_server()
        return 'Shutting down...'


class HealthCheck(View):
    methods = ['GET']

    def dispatch_request(self):
        return jsonify(status='ok')


def all_methods():
    return [
        'GET',
        'HEAD',
        'POST',
        'PUT',
        'DELETE',
        'CONNECT',
        'OPTIONS',
        'TRACE',
        'PATCH'
    ]


def register(app: Type[Flask], path: str, resource: Type[View], **params):
    """Registers a new REST endpoint handler.

    Arguments:
        app (Flask): The Flask application that should host the resource.
        path (str): Relative endpoint path specifier.
        resource (View): Flask view that should handle requests to `path`.
        params (kwargs): All additional arguments that should be passed to View.__init__.
    """
    path = '/{}/{}'.format(app.config['prefix'], path.rstrip('/'))
    path = re.sub(r'//+', '/', path)
    app.add_url_rule(path,
                     view_func=resource.as_view(
                         name=resource.__name__.lower(),
                         **params
                     ))
    LOGGER.info('added route ("{}", {})'.format(path, resource))


def create_app(config: dict) -> Type[Flask]:
    app = Flask(config['name'])
    app.config.update(config)

    register(app, '/_service/shutdown', Shutdown)
    register(app, '/_service/status', HealthCheck)

    return app
