import logging

from brewpi.connector.codecs.time import ScaledTime

from brewpi_service.rest import api
from brewpi_service.plugins import BrewPiServicePlugin
from brewpi_service.database import db_session, get_or_create
from brewpi_service.admin import admin, ModelView

__plugin__ = "ScaledTimeDevicePlugin"

LOGGER = logging.getLogger(__name__)


class ScaledTimeDevicePlugin(BrewPiServicePlugin):
    """
    A Simple plugin that adds support for a Clock Device
    """

    def setup(self):
        from .models import ClockDevice

    def install(self):
        # Admin
        from .models import ClockDevice
        admin.add_view(ModelView(ClockDevice, db_session))

        # Data Syncher
        from brewpi_service.datasync.controlbox import BrewpiEvents
        from .synchers import ScaledTimeSyncher

        BrewpiEvents.handlers[ScaledTime] = ScaledTimeSyncher()

        # REST Api
        from .resources import ClockDeviceResource
        api.add_resource(ClockDeviceResource, '/clock/<int:id>', endpoint='clockdevice_detail')



