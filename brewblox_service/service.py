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
import tempfile
from distutils.util import strtobool
from logging.handlers import TimedRotatingFileHandler
from os import getenv
from typing import List, Optional

from aiohttp import web
from aiohttp_apispec import docs, setup_aiohttp_apispec, validation_middleware

from brewblox_service import brewblox_logger, cors, features

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
        logging.getLogger('asyncio').setLevel(logging.WARN)
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
    parser = argparse.ArgumentParser(fromfile_prefix_chars='@')
    parser.add_argument('-H', '--host',
                        help='Host to which the app binds. [%(default)s]',
                        default='0.0.0.0')
    parser.add_argument('-p', '--port',
                        help='Port to which the app binds. [%(default)s]',
                        default=5000,
                        type=int)
    parser.add_argument('--bind-http-server',
                        help=('Enable or disable all endpoints. '
                              'Set to false for host-mode services without meaningful endpoints. [%(default)s]'),
                        default=True,
                        metavar='true|false',
                        type=lambda v: bool(strtobool(v.lower())))
    parser.add_argument('-o', '--output',
                        help='Logging output. [%(default)s]')
    parser.add_argument('-n', '--name',
                        help='Service name. This will be used as prefix for all endpoints. [%(default)s]',
                        default=default_name)
    parser.add_argument('--debug',
                        help='Run the app in debug mode. [%(default)s]',
                        action='store_true')

    # Deprecated and silently ignored
    parser.add_argument('--eventbus-host', help=argparse.SUPPRESS)
    parser.add_argument('--eventbus-port', help=argparse.SUPPRESS)

    group = parser.add_argument_group('MQTT Event handling')
    group.add_argument('--mqtt-protocol',
                       help='Transport protocol used for MQTT events. [%(default)s]',
                       choices=['mqtt', 'mqtts', 'ws', 'wss'],
                       default='mqtt')
    group.add_argument('--mqtt-host',
                       help='Hostname at which the eventbus can be reached [%(default)s]',
                       default='eventbus')
    group.add_argument('--mqtt-port',
                       help='Port at which the eventbus can be reached [%(default)s]',
                       type=int)
    group.add_argument('--mqtt-path',
                       help='Path used for MQTT events. Only applies if a websockets protocol is used. [%(default)s]',
                       default='/eventbus')
    group.add_argument('--history-topic',
                       help='Eventbus exchange to which logged controller state is broadcast. [%(default)s]',
                       default='brewcast/history')
    group.add_argument('--state-topic',
                       help='Eventbus topic to which volatile controller state is broadcast. [%(default)s]',
                       default='brewcast/state')
    return parser


def create_app(
        default_name: str = None,
        parser: argparse.ArgumentParser = None,
        raw_args: Optional[List[str]] = None
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

    app = web.Application()
    app['config'] = vars(args)
    prefix = '/' + args.name.lstrip('/')

    app.middlewares.append(cors.cors_middleware)
    app.middlewares.append(validation_middleware)

    setup_aiohttp_apispec(
        app=app,
        title=args.name,
        version='v1',
        url=f'{prefix}/api/doc/swagger.json',
        swagger_path=f'{prefix}/api/doc',
        static_path=f'{prefix}/static/swagger',
    )

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
    config = app['config']
    name = config['name']
    prefix = '/' + name.lstrip('/')

    prefixed_paths = [
        f'{prefix}/api/doc/swagger.json',
        f'{prefix}/api/doc',
        f'{prefix}/static/swagger',
    ]

    app.router.add_routes(routes)
    for resource in app.router.resources():
        if resource.canonical not in prefixed_paths:
            resource.add_prefix(prefix)

    LOGGER.info(f'Service name: {name}')
    LOGGER.info(f'Service info: {getenv("SERVICE_INFO")}')
    LOGGER.info(f'Service config: {config}')

    for route in app.router.routes():
        LOGGER.debug(f'Endpoint [{route.method}] {route.resource.canonical}')

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
    config = app['config']

    if config['bind_http_server']:
        web.run_app(app, host=config['host'], port=config['port'])
    else:
        # Listen to a dummy UNIX socket
        # The service still runs, but is not bound to any port
        # This is useful for services without a meaningful REST API
        with tempfile.TemporaryDirectory() as tmpdir:
            web.run_app(app, path=f'{tmpdir}/dummy.sock')


@docs(
    tags=['Service'],
    summary='Service health check',
)
@routes.get('/_service/status')
async def healthcheck(request: web.Request) -> web.Response:
    return web.json_response({'status': 'ok'})
