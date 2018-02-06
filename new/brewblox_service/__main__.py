"""
Entry point for brewblox_service.

Responsible for parsing user configuration, and creating top-level objects.
"""

import sys
from typing import Type

from flask import Flask
from flask_cors import CORS
from flask_marshmallow import Marshmallow

from brewblox_service.rest import Api


def create_app(config: dict) -> Type[Flask]:
    app = Flask('brewblox_service')
    app.config.update(config)

    ma = Marshmallow(app)
    api = Api()

    # TODO(Bob) init all other app components

    CORS(app)
    api.init_app(app)
    ma.init_app(app)

    return app


def main(sys_args: list):
    app = create_app({})
    # TODO(Bob)
    print(app)


if __name__ == '__main__':
    main(sys.argv[1:])
