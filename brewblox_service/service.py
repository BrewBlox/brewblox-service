"""
Generic startup functions for a brewblox application.

Responsible for parsing user configuration, and creating top-level objects.
This module provides the framework to which service implementations can attach their features.

Example:
    # Uses the default argument parser
    # To add new commandline arguments, use create_parser()
    app = service.create_app(default_name='my_service')

    async def setup():
        # (Placeholder names)
        # All features (endpoints and async handlers) must be created and added to the app here
        # The Aiohttp Application will freeze functionality once it has been started
        feature_one.setup(app)
        feature_two.setup(app)

    # Run the application
    # This function blocks until the application is shut down
    service.run_app(app, setup())
"""

import argparse
import logging
# The argumentparser can't fall back to the default sys.argv if sys is not imported
import sys  # noqa
import tempfile
from typing import Awaitable, Optional

from aiohttp import web
from aiohttp_pydantic import oas

from brewblox_service import brewblox_logger, cors, features, models

LOGGER = brewblox_logger(__name__)


def _init_logging(args: argparse.Namespace):
    level = logging.DEBUG if args.debug else logging.INFO
    format = '%(asctime)s %(levelname)-8s %(name)-30s  %(message)s'
    datefmt = '%Y/%m/%d %H:%M:%S'

    logging.basicConfig(level=level, format=format, datefmt=datefmt)
    logging.captureWarnings(True)

    if not args.debug:
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
    parser.add_argument('-n', '--name',
                        help='Service name. This will be used as prefix for all endpoints. [%(default)s]',
                        default=default_name)
    parser.add_argument('--debug',
                        help='Run the app in debug mode. [%(default)s]',
                        action='store_true')

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
        raw_args: Optional[list[str]] = None,
        config_cls: type[models.ServiceConfig] = models.ServiceConfig,
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

        config_cls (type[models.ServiceConfig], optional):
            The Pydantic model to load the parsed args.
            This model should inherit from ServiceConfig.

    Returns:
        web.Application: A configured Aiohttp Application object.
            This Application is not yet running.

    """

    if parser is None:
        assert default_name, 'Default service name is required'
        parser = create_parser(default_name)

    args, unknown_args = parser.parse_known_args(raw_args)
    _init_logging(args)

    if unknown_args:
        LOGGER.error(f'Unknown arguments detected: {unknown_args}')

    config: models.ServiceConfig = config_cls(**vars(args))
    app = web.Application()
    app['config'] = config

    app.middlewares.append(cors.cors_middleware)
    oas.setup(app, url_prefix='/api/doc', title_spec=config.name)

    return app


def run_app(app: web.Application,
            setup: Awaitable = None,
            listen_http: bool = True):
    """
    Runs the application in an async context.
    This function will block indefinitely until the application is shut down.

    Args:
        app (web.Application):
            The Aiohttp Application as created by `create_app()`

        setup (Awaitable):
            If you have setup that should happen async before app start,
            you can provide an awaitable here.
            It will be awaited before application startup.

        listen_http (bool):
            Whether to open a port for the REST API.
            Set to False to disable all REST endpoints.
            This can be useful for services that use communication protocols
            other than REST (such as MQTT), or only have active functionality.
    """
    config: models.ServiceConfig = app['config']

    async def _factory() -> web.Application:
        if setup is not None:
            await setup

        prefix = '/' + config.name.lstrip('/')
        for resource in app.router.resources():
            resource.add_prefix(prefix)

        LOGGER.info(f'Service name: {config.name}')
        LOGGER.info(f'Service config: {config}')

        for route in app.router.routes():
            LOGGER.debug(f'Endpoint [{route.method}] {route.resource.canonical}')

        for name, impl in app.get(features.FEATURES_KEY, {}).items():
            LOGGER.debug(f'Feature [{name}] {impl}')

        return app

    if listen_http:
        web.run_app(_factory(), host=config.host, port=config.port)
    else:
        # Listen to a dummy UNIX socket
        # The service still runs, but is not bound to any port
        # This is useful for services without a meaningful REST API
        with tempfile.TemporaryDirectory() as tmpdir:
            web.run_app(_factory(), path=f'{tmpdir}/dummy.sock')
