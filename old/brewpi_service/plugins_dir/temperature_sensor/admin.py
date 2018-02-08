from brewpi_service.database import db_session
from brewpi_service.admin import admin, ModelView

from .models import TemperatureSensor, PID


class TemperatureSensorAdminView(ModelView):
    column_hide_backrefs = False
    column_exclude_list = ('type',)
    # column_filters = ('controller',)


admin.add_view(TemperatureSensorAdminView(TemperatureSensor,
                                          db_session))


class PIDAdminView(ModelView):
    column_hide_backrefs = True
    column_exclude_list = ('type',)
    # column_filters = ('controller',)


admin.add_view(PIDAdminView(PID,
                            db_session))
