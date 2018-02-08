"""
Entry point for brewblox_service.

Responsible for parsing user configuration, and creating top-level objects.
"""

import argparse
import logging
import sys
from logging.handlers import TimedRotatingFileHandler
from typing import Type

from brewblox_service import rest


def get_args(sys_args: list) -> Type[argparse.Namespace]:
    argparser = argparse.ArgumentParser()
    argparser.add_argument('-p', '--port',
                           help='Port on which the Flask app listens. Default = 5000',
                           default=5000,
                           type=int)
    argparser.add_argument('-o', '--output',
                           help='Logging output. Default = stdout')
    argparser.add_argument('-n', '--name',
                           help='Flask service name. Default = brewblox_service',
                           default='brewblox_service')
    argparser.add_argument('--debug',
                           help='Run the Flask app in debug mode.',
                           action='store_true')
    return argparser.parse_args(sys_args)


def init_logging(args: Type[argparse.Namespace]):
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s %(name)-30s %(levelname)-8s %(message)s',
        datefmt='%y/%m/%d %H:%M:%S'
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


def main(sys_args: list):
    args = get_args(sys_args)
    init_logging(args)

    app_config = {
        'name': args.name
    }

    app = rest.create_app(app_config)
    app.run(port=args.port, debug=args.debug)


if __name__ == '__main__':
    main(sys.argv[1:])
