"""
Entry point for brewblox_service.

Responsible for parsing user configuration, and creating top-level objects.
"""

import argparse
import logging
import sys
from typing import Type

from brewblox_service import rest


def get_args(sys_args: list) -> Type[argparse.Namespace]:
    argparser = argparse.ArgumentParser()
    argparser.add_argument('-o', '--output',
                           help='Logging output. Default = stdout')
    argparser.add_argument('-c', '--config',
                           help='Configuration file.')
    argparser.add_argument('-n', '--name',
                           help='Flask service name. Default = brewblox_service',
                           default='brewblox_service')
    return argparser.parse_args(sys_args)


def init_logging(args: Type[argparse.Namespace]):
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s',
        datefmt='%m-%d %H:%M:%S'
    )

    if args.output:
        handler = logging.handlers.TimedRotatingFileHandler(
            args.output,
            when='d',
            interval=1,
            backupCount=7
        )
        logging.getLogger().addHandler(handler)


def main(sys_args: list):
    args = get_args(sys_args)
    init_logging(args)

    app = rest.create_app({})
    # TODO(Bob)
    print(app)


if __name__ == '__main__':
    main(sys.argv[1:])
