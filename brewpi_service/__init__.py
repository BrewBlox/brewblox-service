import coloredlogs



from flask import Flask

from flask_marshmallow import Marshmallow

coloredlogs.install(level='DEBUG')

app = Flask("brewpi_service")

# FIXME Should be in a configuration file
app.config.update({
    "SECRET_KEY": 'A0Zr98j/3yX R~XHH!jmN]LWX/,?RT',
    "SQLALCHEMY_DATABASE_URI": 'sqlite:///brewpi-service.db'
})

ma = Marshmallow(app)

from . import commands
from .admin import admin
from .controller import models
from .controller.models import Controller
from .controller import resources
from .database import db_session, load_models
from .plugins import plugin_manager
from .rest import api
from .tasks import rq, run_synchers


plugin_manager.init_app(app=app, plugin_folder="plugins_dir")

# Now, let plugins register things
plugin_manager.install_plugins()

# Init application components
api.init_app(app)
admin.init_app(app)

rq.init_app(app)

with app.app_context():
    run_synchers.queue()
