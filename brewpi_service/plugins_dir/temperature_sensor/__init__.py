import logging

from brewpi_service.rest import api
from brewpi_service.plugins.core import BrewPiServicePlugin

__plugin__ = "TemperatureSensorDevicePlugin"

LOGGER = logging.getLogger(__name__)


class TemperatureSensorDevicePlugin(BrewPiServicePlugin):
    """
    A Plugin that adds everything needed for the DS2xxx temperature sensors to
    work with the service.
    """

    def setup(self):
        from .models import TemperatureSensorDevice

    def install(self):
        # Admin
        from . import admin

        # REST Api
        from .models import TemperatureSensorDevice
        from .rest import TemperatureSensorDevice
        from .schemas import TemperatureSensorDeviceSchema
        from brewpi_service.controller.schemas import ControllerDeviceDisambiguator
        ControllerDeviceDisambiguator.class_to_schema[TemperatureSensorDevice.__name__] = TemperatureSensorDeviceSchema
