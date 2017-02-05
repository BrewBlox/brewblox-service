from brewpi_service.database import db_session
from brewpi_service.admin import admin, ModelView

from .models import TemperatureSensorDevice

class TemperatureSensorDeviceAdminView(ModelView):
    column_hide_backrefs = False
    column_exclude_list = ('type',)
    column_filters = ('controller',)


admin.add_view(TemperatureSensorDeviceAdminView(TemperatureSensorDevice,
                                                db_session))
