from flask import Flask
from flask_admin.contrib.sqla import ModelView

from .controller import models # NOQA
from .controller.models import Controller
from .controller.resources import (
    ControllerResource, ControllerListResource
)

from .admin import admin
from .database import db_session, load_models
from .plugins import plugin_manager
from .rest import api

app = Flask("brewpi_service")


# FIXME Should be in settings
app.config.update(
)


# FIXME Should be in settings
app.secret_key = 'A0Zr98j/3yX R~XHH!jmN]LWX/,?RT'

plugin_manager.init_app(app=app, plugin_folder="plugins_dir")

# Add basic models to admin
admin.add_view(ModelView(Controller, db_session))

# Add models to API
api.add_resource(ControllerResource, '/controllers/<string:id>', endpoint='controllers_detail')
api.add_resource(ControllerListResource, '/controllers', endpoint='controllers_list')

# Now, let's plugin register things
plugin_manager.install_plugins()

# Init application components
api.init_app(app)
admin.init_app(app)

from .tasks import rq, run_synchers

rq.init_app(app)

with app.app_context():
    run_synchers.queue()

@app.teardown_appcontext
def shutdown_session(exception=None):
    db_session.remove()
