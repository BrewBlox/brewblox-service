"""
Generic startup functions for a brewblox application.

Responsible for parsing user configuration, and creating top-level objects.
This module provides the framework to which service implementations can attach their features.

Example:
    # Uses the default argument parser
    # To add new commandline arguments, use create_parser()
    app = service.create_app(default_name='my_service')

    # (Placeholder names)
    # All features (endpoints and async handlers) must be created and added to the app here
    # The Aiohttp Application will freeze functionality once it has been started
    feature_one.setup(app)
    feature_two.setup(app)

    # Modify added resources to conform to standards
    service.furnish(app)

    # Run the application
    # This function blocks until the application is shut down
    service.run(app)
"""

import argparse
import logging
# The argumentparser can't fall back to the default sys.argv if sys is not imported
import sys  # noqa
import warnings
from logging.handlers import TimedRotatingFileHandler
from os import getenv
from typing import List

import aiohttp_swagger
from aiohttp import web

from brewblox_service import brewblox_logger, cors_middleware, features

LOGGER = brewblox_logger(__name__)
routes = web.RouteTableDef()


def _init_logging(args: argparse.Namespace):
    level = logging.DEBUG if args.debug else logging.INFO
    format = '%(asctime)s %(levelname)-8s %(name)-30s  %(message)s'
    datefmt = '%Y/%m/%d %H:%M:%S'

    logging.basicConfig(level=level, format=format, datefmt=datefmt)

    if args.output:
        handler = TimedRotatingFileHandler(
            args.output,
            when='d',
            interval=1,
            backupCount=7,
            encoding='utf-8'
        )
        handler.setFormatter(logging.Formatter(format, datefmt))
        handler.setLevel(level)
        logging.getLogger().addHandler(handler)

    if not args.debug:
        logging.getLogger('aioamqp').setLevel(logging.WARN)
        logging.getLogger('asyncio').setLevel(logging.CRITICAL)
        logging.getLogger('aiohttp.access').setLevel(logging.WARN)


def create_parser(default_name: str) -> argparse.ArgumentParser:
    """
    Creates the default brewblox_service ArgumentParser.
    Service-agnostic arguments are added.

    The parser allows calling code to add additional arguments before using it in create_app()

    Args:
        default_name (str):
            default value for the --name commandline argument.

    Returns:
        argparse.ArgumentParser: a Python ArgumentParser with defaults set.

    """
    argparser = argparse.ArgumentParser(fromfile_prefix_chars='@')
    argparser.add_argument('-H', '--host',
                           help='Host to which the app binds. [%(default)s]',
                           default='0.0.0.0')
    argparser.add_argument('-p', '--port',
                           help='Port to which the app binds. [%(default)s]',
                           default=5000,
                           type=int)
    argparser.add_argument('-o', '--output',
                           help='Logging output. [%(default)s]')
    argparser.add_argument('-n', '--name',
                           help='Service name. This will be used as prefix for all endpoints. [%(default)s]',
                           default=default_name)
    argparser.add_argument('--debug',
                           help='Run the app in debug mode. [%(default)s]',
                           action='store_true')
    argparser.add_argument('--eventbus-host',
                           help='Hostname at which the eventbus can be reached [%(default)s]',
                           default='eventbus')
    argparser.add_argument('--eventbus-port',
                           help='Port at which the eventbus can be reached [%(default)s]',
                           default=5672,
                           type=int)
    return argparser


def create_app(
        default_name: str = None,
        parser: argparse.ArgumentParser = None,
        raw_args: List[str] = None
) -> web.Application:
    """
    Creates and configures an Aiohttp application.

    Args:
        default_name (str, optional):
            Default value for the --name commandline argument.
            This value is required if `parser` is not provided.
            This value will be ignored if `parser` is provided.

        parser (argparse.ArgumentParser, optional):
            Application-specific parser.
            If not provided, the return value of `create_parser()` will be used.

        raw_args (list of str, optional):
            Explicit commandline arguments.
            Defaults to sys.argv[1:]

    Returns:
        web.Application: A configured Aiohttp Application object.
            This Application must be furnished, and is not yet running.

    """

    if parser is None:
        assert default_name, 'Default service name is required'
        parser = create_parser(default_name)

    args = parser.parse_args(raw_args)
    _init_logging(args)

    LOGGER.info(f'Creating [{args.name}] application')
    app = web.Application()
    app['config'] = vars(args)
    return app


def furnish(app: web.Application):
    """
    Configures Application routes, readying it for running.

    This function modifies routes and resources that were added by calling code,
    and must be called immediately prior to `run(app)`.

    Args:
        app (web.Application):
            The Aiohttp Application as created by `create_app()`
    """
    app_name = app['config']['name']
    prefix = '/' + app_name.lstrip('/')
    app.router.add_routes(routes)
    cors_middleware.enable_cors(app)

    # Configure CORS and prefixes on all endpoints.
    known_resources = set()
    for route in list(app.router.routes()):
        if route.resource in known_resources:
            continue
        known_resources.add(route.resource)
        route.resource.add_prefix(prefix)

    # Configure swagger settings
    # We set prefix explicitly here
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        aiohttp_swagger.setup_swagger(app,
                                      swagger_url=prefix + '/api/doc',
                                      description='',
                                      title=f'Brewblox Service "{app_name}"',
                                      api_version='0.0',
                                      contact='development@brewpi.com')

    LOGGER.info('Service info: ' + getenv('SERVICE_INFO', 'UNKNOWN'))

    for route in app.router.routes():
        LOGGER.debug(f'Endpoint [{route.method}] {route.resource}')

    for name, impl in app.get(features.FEATURES_KEY, {}).items():
        LOGGER.debug(f'Feature [{name}] {impl}')


def run(app: web.Application):
    """
    Runs the application in an async context.
    This function will block indefinitely until the application is shut down.

    Args:
        app (web.Application):
            The Aiohttp Application as created by `create_app()`
    """
    host = app['config']['host']
    port = app['config']['port']

    # starts app. run_app() will automatically start the async context.
    web.run_app(app, host=host, port=port)


@routes.get('/_service/status')
async def healthcheck(request: web.Request) -> web.Response:
    """
    ---
    tags:
    - Service
    summary: health check
    description: Returns service health.
    operationId: _service.status
    produces:
    - application/json
    responses:
    "200":
        description: successful operation
    """
    return web.json_response({'status': 'ok'})
