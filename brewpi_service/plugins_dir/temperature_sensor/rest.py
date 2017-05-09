from flask import jsonify

from brewpi_service.rest import (
    api_v1,
    marshal_with, MethodResource
)

from .models import TemperatureSensor, PID
from .schemas import (
    TemperatureSensorSchema,
    PIDSchema,
)

# -- Temperature Sensor
@marshal_with(TemperatureSensorSchema(many=True))
class TemperatureSensorList(MethodResource):
    """
    List Temperature Sensors
    """
    def get(self, **kwargs):
        return TemperatureSensor.query.all()

api_v1.register('/temperature_sensors/', TemperatureSensorList)


@marshal_with(TemperatureSensorSchema)
class TemperatureSensorDetail(MethodResource):
    """
    Detail a given Temperature Sensor
    """
    def get(self, id, **kwargs):
        return TemperatureSensor.query.get(id)

api_v1.register('/temperature_sensors/<id>/', TemperatureSensorDetail)


# -- PID
@marshal_with(PIDSchema(many=True))
class PIDList(MethodResource):
    """
    List PIDs
    """
    def get(self, **kwargs):
        return PID.query.all()

api_v1.register('/pids/', PIDList)


@marshal_with(PIDSchema)
class PIDDetail(MethodResource):
    """
    Detail a given PID
    """
    def get(self, id, **kwargs):
        return PID.query.get(id)

api_v1.register('/pids/<id>/', PIDDetail)
