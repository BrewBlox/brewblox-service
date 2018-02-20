"""
Generic startup for a brewblox application.

Responsible for parsing user configuration, and creating top-level objects.
"""

import argparse
import logging
from logging.handlers import TimedRotatingFileHandler
from typing import Type

from aiohttp import web
import sys
from brewblox_service import announcer


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


def parse_args(sys_args: list) -> Type[argparse.Namespace]:
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
                           ' Defaults to application name (argv[0]) or "brewblox"',
                           default=sys_args[0] if len(sys_args) else 'brewblox')
    argparser.add_argument('--debug',
                           help='Run the app in debug mode.',
                           action='store_true')
    argparser.add_argument('-g', '--gateway',
                           help='Gateway URL. Services will be announced here. Default = http://localhost:8081',
                           default='http://localhost:8081')
    return argparser.parse_args(sys_args)


def create(args: Type[argparse.Namespace]=None) -> Type[web.Application]:
    if args is None:
        args = parse_args(sys.argv)

    _init_logging(args)

    config = {
        'name': args.name,
        'host': args.host,
        'port': args.port,
        'gateway': args.gateway
    }

    app = web.Application()
    app.config = config
    return app


async def furnish(app: Type[web.Application]) -> Type[web.Application]:
    app.router.add_routes(routes)

    # TODO(Bob): CORS support
    # TODO(Bob): swagger register routes
    await announcer.announce(app)


async def run(app: Type[web.Application]):
    host = app.config['host']
    port = app.config['port']

    web.run_app(app, host=host, port=port)
