from brewpi_service import ma

from brewpi_service.controller.schemas import (
    ControllerLoopSchema,
    ControllerDeviceSchema
)

from .models import TemperatureSensorDevice, PID


class TemperatureSensorDeviceSchema(ControllerDeviceSchema):
    """
    Serialization schema for the TemperatureSensorDevice
    """
    class Meta:
        model = TemperatureSensorDevice
        fields = ('id', 'value', 'url')

    url = ma.AbsoluteUrlFor('temperaturesensordevicedetail', id='<id>')


class PIDLoopSchema(ControllerLoopSchema):
    """
    Serialization schema for the PID Loop algorithm
    """
    class Meta:
        model = PID
        fields = ('id', 'input', 'actuator', 'setpoint', 'url')

    url = ma.AbsoluteUrlFor('pidloopdetail', id='<id>')
