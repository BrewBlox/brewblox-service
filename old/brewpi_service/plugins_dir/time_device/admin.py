from brewpi_service.database import db_session
from brewpi_service.admin import admin, ModelView

from .models import ClockDevice


class ClockDeviceAdminView(ModelView):
    column_hide_backrefs = False
    column_exclude_list = ('type',)
    # column_filters = ('controller',)


admin.add_view(ClockDeviceAdminView(ClockDevice, db_session))
