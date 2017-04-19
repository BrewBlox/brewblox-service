from basicevents import run as run_events
import coloredlogs

from flask import Flask
from flask_marshmallow import Marshmallow
from apispec import APISpec

coloredlogs.install(level='DEBUG')

app = Flask("brewpi_service")

# FIXME Should be in a configuration file
app.config.update({
    'APISPEC_SPEC': APISpec(
        title='BrewPi Service',
        version='0.1',
        plugins=['apispec.ext.marshmallow']
    ),
    'APISPEC_SWAGGER_URL': '/specs.json',
    'APISPEC_SWAGGER_UI_URL': None,
    "SECRET_KEY": 'A0Zr98j/3yX R~XHH!jmN]LWX/,?RT',
    "SQLALCHEMY_DATABASE_URI": 'sqlite:///brewpi-service.db'
})

ma = Marshmallow(app)

from . import commands
from .admin import admin
from . import controller
from .controller.models import ControllerDevice
from .database import db_session, load_models
from .plugins.core import plugin_manager
from .plugins.rest import *
from . import rest
from .tasks import rq, run_synchers
from .controller import rest
from .rest import api_v1, specs as api_specs


plugin_manager.init_app(app=app, plugin_folder="plugins_dir")

# Now, let plugins register things
plugin_manager.install_plugins()

api_specs.init_app(app)
api_v1.init_app(app)

# Init application components
admin.init_app(app)

rq.init_app(app)


# Start the event process
run_events()

with app.app_context():
    run_synchers.queue()
