"""
Generic startup for a brewblox application.

Responsible for parsing user configuration, and creating top-level objects.
"""

import argparse
import asyncio
import logging
import sys  # noqa
from logging.handlers import TimedRotatingFileHandler
from typing import Type

import aiohttp_cors
import aiohttp_swagger
from aiohttp import web

from brewblox_service import announcer

LOGGER = logging.getLogger(__name__)
routes = web.RouteTableDef()


@routes.get('/_service/status')
async def healthcheck(request: Type[web.Request]) -> Type[web.Response]:
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

    if not args.debug:
        logging.getLogger('pika').setLevel(logging.CRITICAL)
        logging.getLogger('pika.adapters.base_connection').setLevel(logging.CRITICAL)
        logging.getLogger('aio_pika.robust_connection').setLevel(logging.CRITICAL)
        logging.getLogger('asyncio').setLevel(logging.CRITICAL)


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
    prefix = '/' + app['config']['name'].lstrip('/')
    app.router.add_routes(routes)

    # Configure default CORS settings.
    cors = aiohttp_cors.setup(app, defaults={
        "*": aiohttp_cors.ResourceOptions(
            allow_credentials=True,
            expose_headers="*",
            allow_headers="*",
        )
    })

    # Configure CORS and prefixes on all endpoints.
    known_resources = set()
    for route in list(app.router.routes()):
        if route.resource in known_resources:
            continue

        # Add to known
        known_resources.add(route.resource)

        # Add prefix
        route.resource.add_prefix(prefix)

        # Add CORS
        # TODO(Bob): Remove static resource instance check when aiohttp-cors bug is fixed
        # Issue: https://github.com/aio-libs/aiohttp-cors/issues/155
        if not isinstance(route.resource, web.StaticResource):
            cors.add(route)
            LOGGER.debug(f'Enabled CORS for {route.resource}')

    # Configure swagger settings
    # We set prefix explicitly here
    aiohttp_swagger.setup_swagger(app,
                                  swagger_url=prefix + '/api/doc',
                                  description='',
                                  title='Brewblox Service',
                                  api_version='0.3.0',
                                  contact='development@brewpi.com')

    for route in app.router.routes():
        LOGGER.info(f'Registered [{route.method}] {route.resource}')

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
