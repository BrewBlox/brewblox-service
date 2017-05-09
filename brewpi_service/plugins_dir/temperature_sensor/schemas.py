from brewpi_service import ma

from brewpi_service.controller.schemas import (
    ControllerBlockSchema,
)

from .models import (
    TemperatureSensor,
    PID,
    SensorSetpointPair
)

from .interfaces import (
    IProcessValue,
    ISensor,
    IPID
)

from zope.interface import implementer


@implementer(IProcessValue)
class SensorSetpointPair(ControllerBlockSchema):
    """
    A simple pair of a Sensor and a Setpoint
    """
    class Meta:
        model = SensorSetpointPair


@implementer(ISensor)
class TemperatureSensorSchema(ControllerBlockSchema):
    """
    Serialization schema for the TemperatureSensor
    """
    class Meta:
        model = TemperatureSensor
        fields = ('id', 'value', 'url')

    url = ma.AbsoluteUrlFor('temperaturesensor.details_view', id='<id>')


@implementer(IPID)
class PIDSchema(ControllerBlockSchema):
    """
    Serialization schema for the PID Loop algorithm
    """
    class Meta:
        model = PID
        fields = ('id', 'input', 'actuator', 'setpoint', 'url')

    url = ma.AbsoluteUrlFor('pid.details_view', id='<id>')
