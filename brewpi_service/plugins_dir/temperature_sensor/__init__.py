import logging

from brewpi_service.plugins.core import BrewPiServicePlugin

__plugin__ = "TemperatureSensorDevicePlugin"

LOGGER = logging.getLogger(__name__)


class TemperatureSensorDevicePlugin(BrewPiServicePlugin):
    """
    A Plugin that adds everything needed for the DS2xxx temperature sensors to
    work with the service.
    """

    def setup(self):
        from .models import TemperatureSensorDevice # noqa
        from .models import PID # noqa

    def install(self):
        # Admin
        from . import admin

        # REST Api
        from .rest import TemperatureSensorDevice, PID
        from .schemas import TemperatureSensorDeviceSchema, PIDLoopSchema
        from brewpi_service.controller.schemas import ControllerDeviceDisambiguator, ControllerLoopDisambiguator
        ControllerDeviceDisambiguator.class_to_schema[TemperatureSensorDevice.__name__] = TemperatureSensorDeviceSchema

        ControllerLoopDisambiguator.class_to_schema[PID.__name__] = PIDLoopSchema
