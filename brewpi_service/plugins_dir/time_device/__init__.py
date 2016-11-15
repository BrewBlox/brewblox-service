import logging

from brewpi.connector.codecs.time import ScaledTime

from brewpi_service.plugins import BrewPiServicePlugin
from brewpi_service.database import db_session, get_or_create
from brewpi_service.admin import admin, ModelView

__plugin__ = "TimeDevicePlugin"

LOGGER = logging.getLogger(__name__)


class TimeDevicePlugin(BrewPiServicePlugin):
    """
    A Simple plugin that adds support for a Clock Device
    """

    def setup(self):
        from .models import ClockDevice

    def install(self):
        from .models import ClockDevice
        admin.add_view(ModelView(ClockDevice, db_session))

        from brewpi_service.datasync.controlbox import BrewpiEvents
        from .synchers import ScaledTimeSyncher

        BrewpiEvents.handlers[ScaledTime] = ScaledTimeSyncher()



