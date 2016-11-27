from brewpi_service.admin import admin, ModelView
from brewpi_service.database import db_session

from .models import Controller

# Add basic models to admin
admin.add_view(ModelView(Controller, db_session))
