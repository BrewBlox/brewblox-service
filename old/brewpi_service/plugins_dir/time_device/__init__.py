import logging

# from brewpi.controlbox.codecs.time import ScaledTime

from brewpi_service.plugins.core import BrewPiServicePlugin

__plugin__ = "ScaledTimeDevicePlugin"

LOGGER = logging.getLogger(__name__)


class ScaledTimeDevicePlugin(BrewPiServicePlugin):
    """
    A Simple plugin that adds support for a Clock Device
    """

    def setup(self):
        from .models import ClockDevice # noqa

    def install(self):
        # Admin
        from . import admin # noqa

        # Data Syncher
        # from brewpi_service.datasync.controlbox import BrewpiEvents
        # from .synchers import ScaledTimeSyncher

        # BrewpiEvents.handlers[ScaledTime] = ScaledTimeSyncher()

        # REST Api
        from .rest import ClockDevice
        from .schemas import ClockSchema
        from brewpi_service.controller.schemas import ControllerBlockDisambiguator
        ControllerBlockDisambiguator.class_to_schema[ClockDevice.__name__] = ClockSchema
        # print(ControllerDeviceDisambiguator.class_to_schema)
        # api.add_resource(ClockDeviceResource, '/clock/<int:id>', endpoint='clockdevice_detail')
