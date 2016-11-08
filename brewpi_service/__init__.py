from flask import Flask
from flask_admin.contrib.sqla import ModelView

from .controller import models # NOQA
from .controller.models import Controller
from .controller.resources import (
    ControllerResource, ControllerListResource
)

from .admin import admin
from .database import db_session
from .plugins import plugin_manager
from .rest import api


app = Flask("brewpi-service")


# FIXME Should be in settings
app.config.update(
    CELERY_BROKER_URL='redis://localhost:6379',
    CELERY_RESULT_BACKEND='redis://localhost:6379'
)

# FIXME Should be in settings
app.secret_key = 'A0Zr98j/3yX R~XHH!jmN]LWX/,?RT'


# Add basic models to admin
admin.add_view(ModelView(Controller, db_session))

# Add models to API
api.add_resource(ControllerResource, '/controllers/<string:id>', endpoint='controllers_detail')
api.add_resource(ControllerListResource, '/controllers', endpoint='controllers_list')


# Init application components
api.init_app(app)
plugin_manager.init_app(app)
admin.init_app(app)


@app.teardown_appcontext
def shutdown_session(exception=None):
    db_session.remove()
