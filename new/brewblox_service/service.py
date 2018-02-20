"""
Generic startup for a brewblox application.

Responsible for parsing user configuration, and creating top-level objects.
"""

import argparse
import logging
from logging.handlers import TimedRotatingFileHandler
from typing import Type

from aiohttp import web
import sys  # noqa
from brewblox_service import announcer
import asyncio
import aiohttp_swagger
import aiohttp_cors

LOGGER = logging.getLogger(__name__)
routes = web.RouteTableDef()


@routes.get('/_service/status')
async def healthcheck(request: Type[web.Request]) -> Type[web.Response]:
    """
    Description end-point

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


def _init_logging(args: Type[argparse.Namespace]):
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


def parse_args(sys_args: list=None) -> Type[argparse.Namespace]:
    argparser = argparse.ArgumentParser()
    argparser.add_argument('-H', '--host',
                           help='Host to which the app binds. [%(default)s]',
                           default='localhost')
    argparser.add_argument('-p', '--port',
                           help='Port to which the app binds. [%(default)s]',
                           default=5000,
                           type=int)
    argparser.add_argument('-o', '--output',
                           help='Logging output. [%(default)s]')
    argparser.add_argument('-n', '--name',
                           help='Custom service name. This will be used as prefix in the gateway. [%(default)s]',
                           default='brewblox')
    argparser.add_argument('--debug',
                           help='Run the app in debug mode. [%(default)s]',
                           action='store_true')
    argparser.add_argument('-g', '--gateway',
                           help='Gateway URL. Services will be announced here. [%(default)s]',
                           default='http://localhost:8081')
    return argparser.parse_args(sys_args)


def create(args: Type[argparse.Namespace]=None) -> Type[web.Application]:
    if args is None:
        # parse system args
        args = parse_args()

    _init_logging(args)

    config = {
        'name': args.name,
        'host': args.host,
        'port': args.port,
        'gateway': args.gateway,
        'debug': args.debug,
    }

    LOGGER.info(f'Creating [{args.name}] application')
    app = web.Application(debug=args.debug)
    app['config'] = config
    return app


def furnish(app: Type[web.Application]):
    app.router.add_routes(routes)

    # Configure default CORS settings.
    cors = aiohttp_cors.setup(app, defaults={
        "*": aiohttp_cors.ResourceOptions(
                allow_credentials=True,
                expose_headers="*",
                allow_headers="*",
            )
    })

    # Configure swagger settings
    aiohttp_swagger.setup_swagger(app,
                                  description='',
                                  title='Brewblox Service',
                                  api_version='0.3.0',
                                  contact='development@brewpi.com')

    for route in app.router.routes():
        LOGGER.info(f'Registered [{route.method}] {route.resource}')

    # Configure CORS on all routes.
    for route in list(app.router.routes()):
        if not isinstance(route.resource, web.StaticResource):
            try:
                cors.add(route)
                LOGGER.info(f'Enabled CORS for {route.resource}')
            except RuntimeError:
                # Endpoint routes will re-occur in the list when they support multiple methods.
                # Trying to overwrite the OPTIONS handler for an endpoint triggers a RuntimeError.
                # This can be safely ignored.
                LOGGER.debug(f'Skipped CORS for [{route.method}] {route.resource}')

    # service functions are intentionally synchronous
    # - web.run_app() assumes it is called from a synchronous context
    # - pre-start performance / concurrency is not relevant
    #
    # announcer.announce() is technically async (it uses aiohttp client)
    # asyncio.ensure_future() correctly handles desired behavior (async call in sync function)
    asyncio.ensure_future(announcer.announce(app))


def run(app: Type[web.Application]):
    host = app['config']['host']
    port = app['config']['port']

    # starts app. run_app() will automatically start the async context.
    web.run_app(app, host=host, port=port)
