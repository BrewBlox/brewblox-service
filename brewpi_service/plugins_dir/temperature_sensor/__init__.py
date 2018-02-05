import logging

from brewpi_service.plugins.core import BrewPiServicePlugin

__plugin__ = "TemperatureSensorPlugin"

LOGGER = logging.getLogger(__name__)


class TemperatureSensorPlugin(BrewPiServicePlugin):
    """
    A Plugin that adds everything needed for the DS2xxx temperature sensors to
    work with the service.
    """

    def setup(self):
        from .models import TemperatureSensor # noqa
        from .models import PID # noqa
        from .models import SensorSetpointPair # noqa

    def install(self):
        # Admin
        from . import admin

        # REST Api
        from .models import TemperatureSensor, PID, SetpointSimple, SensorSetpointPair
        from .schemas import TemperatureSensorSchema, PIDSchema, SetpointSimpleSchema, SensorSetpointPairSchema
        from brewpi_service.controller.schemas import ControllerBlockDisambiguator

        ControllerBlockDisambiguator.class_to_schema[SensorSetpointPair.__name__] = SensorSetpointPairSchema
        ControllerBlockDisambiguator.class_to_schema[TemperatureSensor.__name__] = TemperatureSensorSchema
        ControllerBlockDisambiguator.class_to_schema[PID.__name__] = PIDSchema
        ControllerBlockDisambiguator.class_to_schema[SetpointSimple.__name__] = SetpointSimpleSchema

