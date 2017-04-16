from brewpi_service.database import db_session
from brewpi_service.admin import admin, ModelView

from .models import TemperatureSensorDevice, PID


class TemperatureSensorDeviceAdminView(ModelView):
    column_hide_backrefs = False
    column_exclude_list = ('type',)
    column_filters = ('controller',)


admin.add_view(TemperatureSensorDeviceAdminView(TemperatureSensorDevice,
                                                db_session))


class PIDAdminView(ModelView):
    column_hide_backrefs = True
    column_exclude_list = ('type',)
    column_filters = ('controller',)


admin.add_view(PIDAdminView(PID,
                            db_session))
