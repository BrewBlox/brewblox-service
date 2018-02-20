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


routes = web.RouteTableDef()


@routes.get('/_service/status')
async def healthcheck(request: Type[web.Request]) -> Type[web.Response]:
    return web.json_response({'status': 'ok'})


def _init_logging(args: Type[argparse.Namespace]):
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s %(levelname)-8s %(name)-30s  %(message)s',
        datefmt='%Y/%m/%d %H:%M:%S'
    )

    if args.output:
        handler = TimedRotatingFileHandler(
            args.output,
            when='d',
            interval=1,
            backupCount=7,
            encoding='utf-8'
        )
        logging.getLogger().addHandler(handler)


def parse_args(sys_args: list=None) -> Type[argparse.Namespace]:
    argparser = argparse.ArgumentParser()
    argparser.add_argument('-H', '--host',
                           help='Host to which the app binds. Default = localhost',
                           default='localhost')
    argparser.add_argument('-p', '--port',
                           help='Port to which the app binds. Default = 5000',
                           default=5000,
                           type=int)
    argparser.add_argument('-o', '--output',
                           help='Logging output. Default = stdout')
    argparser.add_argument('-n', '--name',
                           help='Custom service name. This will be used as prefix in the gateway.'
                           ' Defaults = brewblox',
                           default='brewblox')
    argparser.add_argument('--debug',
                           help='Run the app in debug mode.',
                           action='store_true')
    argparser.add_argument('-g', '--gateway',
                           help='Gateway URL. Services will be announced here. Default = http://localhost:8081',
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
        'gateway': args.gateway
    }

    app = web.Application()
    app['config'] = config
    return app


def furnish(app: Type[web.Application]) -> Type[web.Application]:
    app.router.add_routes(routes)

    # TODO(Bob): CORS support
    # TODO(Bob): swagger register routes
    # TODO(Bob): admin dashboard / dev tools

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
