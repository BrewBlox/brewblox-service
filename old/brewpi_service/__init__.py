import coloredlogs

from flask import Flask
from flask_marshmallow import Marshmallow
from flask_cors import CORS
from apispec import APISpec

coloredlogs.install(level='DEBUG')

# FIXME Should be in a configuration file

CONFIG = {
    'APISPEC_SPEC': APISpec(
        title='BrewPi Service',
        version='0.1',
        plugins=['apispec.ext.marshmallow']
    ),
    'APISPEC_SWAGGER_URL': '/specs.json',
    'APISPEC_SWAGGER_UI_URL': None,
    "SECRET_KEY": 'A0Zr98j/3yX R~XHH!jmN]LWX/,?RT',
    "DATABASE_URI": 'postgresql+psycopg2://bbox_service:bbox_service@localhost/bbox_service',
    "RQ_REDIS_URL": "redis://localhost:6379",
    "SSE_REDIS_URL": "redis://localhost"
}

app = Flask("brewpi_service")
app.config.update(CONFIG)

from .tasks import rq
rq.init_app(app)

ma = Marshmallow(app)


from . import commands

from . import controller
from .controller.models import ControllerBlock
from .database import db_session, load_models

from .plugins.rest import *
from . import rest

from .controller import rest


def create_front_app():
    cors = CORS(app)

    from . import sse

    from .plugins.core import plugin_manager
    plugin_manager.init_app(app=app, plugin_folder="plugins_dir")


    from .rest import api_v1, specs as api_specs
    api_specs.init_app(app)
    api_v1.init_app(app)

    # Now, let plugins register things
    plugin_manager.install_plugins()


    # Init application components
    from .admin import admin
    admin.init_app(app)

    return app

create_front_app()



