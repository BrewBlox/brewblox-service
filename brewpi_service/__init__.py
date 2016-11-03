from flask import Flask
from flask_admin import Admin
from flask_admin.contrib.sqla import ModelView

from .controller import models # NOQA
from .controller.models import Controller
from .database import db_session


app = Flask("brewpi-service")

# FIXME Should be in settings
app.config.update(
    CELERY_BROKER_URL='redis://localhost:6379',
    CELERY_RESULT_BACKEND='redis://localhost:6379'
)

# FIXME Should be in settings
app.secret_key = 'A0Zr98j/3yX R~XHH!jmN]LWX/,?RT'

admin = Admin(app, name='BrewPi Service', template_mode='bootstrap3')

# Add basic models to admin
admin.add_view(ModelView(Controller, db_session))


@app.teardown_appcontext
def shutdown_session(exception=None):
    db_session.remove()
