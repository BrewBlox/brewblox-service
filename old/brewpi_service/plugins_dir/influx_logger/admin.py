from brewpi_service.database import db_session
from brewpi_service.admin import admin, ModelView

from .models import LoggedDeviceConfiguration


class LoggedDeviceConfigurationAdminView(ModelView):
    column_hide_backrefs = False


admin.add_view(LoggedDeviceConfigurationAdminView(LoggedDeviceConfiguration,
                                                  db_session))
