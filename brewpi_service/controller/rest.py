from flask_apispec import MethodResource
from flask_apispec import marshal_with

from brewpi_service.rest import api_v1

from .models import Controller, ControllerDevice
from .schemas import (
    ControllerSchema,
    ControllerDeviceSchema
)


@marshal_with(ControllerSchema(many=True))
class ControllerList(MethodResource):
    def get(self, **kwargs):
        return Controller.query.all()

api_v1.register('/controllers/', ControllerList)


@marshal_with(ControllerSchema)
class ControllerDetail(MethodResource):
    def get(self, id):
        return Controller.query.get(id)

api_v1.register('/controllers/<id>/', ControllerDetail)


@marshal_with(ControllerDeviceSchema(many=True))
class ControllerDeviceList(MethodResource):
    def get(self):
        return ControllerDevice.query.all()

api_v1.register('/controllers/devices/', ControllerDeviceList)


@marshal_with(ControllerDevice)
class ControllerDeviceDetail(MethodResource):
    def get(self, id):
        return ControllerDevice.query.get(id)

api_v1.register('/controllers/devices/<id>/', ControllerDeviceDetail)
