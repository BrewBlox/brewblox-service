from flask import jsonify

from brewpi_service.rest import (
    api_v1,
    marshal_with, MethodResource
)

from .models import TemperatureSensorDevice, PID
from .schemas import (
    TemperatureSensorDeviceSchema,
    PIDLoopSchema,
)


@marshal_with(TemperatureSensorDeviceSchema(many=True))
class TemperatureSensorDeviceList(MethodResource):
    """
    List Temperature Sensors
    """
    def get(self, **kwargs):
        return TemperatureSensorDevice.query.all()

api_v1.register('/temperature_sensors/', TemperatureSensorDeviceList)


@marshal_with(TemperatureSensorDeviceSchema)
class TemperatureSensorDeviceDetail(MethodResource):
    """
    Detail a given Temperature Sensor
    """
    def get(self, id, **kwargs):
        return TemperatureSensorDevice.query.get(id)

api_v1.register('/temperature_sensors/<id>/', TemperatureSensorDeviceDetail)


# -- PID
@marshal_with(PIDLoopSchema(many=True))
class PIDLoopList(MethodResource):
    """
    List PIDs
    """
    def get(self, **kwargs):
        return PID.query.all()

api_v1.register('/pids/', PIDLoopList)


@marshal_with(PIDLoopSchema)
class PIDLoopDetail(MethodResource):
    """
    Detail a given PID
    """
    def get(self, id, **kwargs):
        return PID.query.get(id)

api_v1.register('/pids/<id>/', PIDLoopDetail)
