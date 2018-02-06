from marshmallow import fields
from brewpi_service import ma

from brewpi_service.controller.schemas import (
    ControllerBlockSchema,
)

from brewpi_service.controller.fields import ControllerData

from .models import (
    TemperatureSensor,
    PID,
    SensorSetpointPair,
    SetpointSimple
)

from .interfaces import (
    ISensor,
    ISetpoint,
    ISensorSetpointPair,
    IPID
)

from zope.interface import implementer


@implementer(ISetpoint)
class SetpointSimpleSchema(ControllerBlockSchema):
    """
    A Simple setpoint
    """
    class Meta:
        model = SetpointSimple
        fields = ControllerBlockSchema.Meta.fields + ('value',)

    value = ControllerData(attribute='value')

@implementer(ISensorSetpointPair)
class SensorSetpointPairSchema(ControllerBlockSchema):
    """
    A simple pair of a Sensor and a Setpoint
    """
    class Meta:
        model = SensorSetpointPair
        fields = ControllerBlockSchema.Meta.fields


@implementer(ISensor)
class TemperatureSensorSchema(ControllerBlockSchema):
    """
    Serialization schema for the TemperatureSensor
    """
    class Meta:
        model = TemperatureSensor
        fields = ControllerBlockSchema.Meta.fields + ('value', 'url')

    value = ControllerData(attribute='value')


@implementer(IPID)
class PIDSchema(ControllerBlockSchema):
    """
    Serialization schema for the PID Loop algorithm
    """
    class Meta:
        model = PID
        fields = ControllerBlockSchema.Meta.fields + ('url', 'kp')

    kp = ControllerData(attribute='kp')

    # actuator = ma.AbsoluteUrlFor('controllerblockdetail', id='<actuator_id>')
    # setpoint = ma.HyperlinkRelated('controllerblockdetail')
    # input = ma.HyperlinkRelated('controllerblockdetail')
