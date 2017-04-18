from flask_apispec import MethodResource
from flask_apispec import marshal_with

from brewpi_service import app
from brewpi_service.rest import specs

from .models import Controller, ControllerDevice
from .schemas import (
    ControllerSchema,
    ControllerDeviceSchema
)

@marshal_with(ControllerSchema(many=True))
class ControllerList(MethodResource):
    def get(self, **kwargs):
        return Controller.query.all()

app.add_url_rule('/controllers/', view_func=ControllerList.as_view(name="controllerlist"))
specs.register(ControllerList)


@marshal_with(ControllerSchema)
class ControllerDetail(MethodResource):
    def get(self, id):
        return Controller.query.get(id)

app.add_url_rule('/controllers/<id>/', view_func=ControllerDetail.as_view(name="controllerdetail"))
specs.register(ControllerDetail)


@marshal_with(ControllerDeviceSchema(many=True))
class ControllerDeviceList(MethodResource):
    def get(self):
        return ControllerDevice.query.all()

app.add_url_rule('/controllers/devices/', view_func=ControllerDeviceList.as_view(name="controllerdevicelist"))
specs.register(ControllerDeviceList)


@marshal_with(ControllerDevice)
class ControllerDeviceDetail(MethodResource):
    def get(self, id):
        return ControllerDevice.query.get(id)

app.add_url_rule('/controllers/devices/<id>/', view_func=ControllerDeviceDetail.as_view(name="controllerdevicedetail"))
specs.register(ControllerDetail)
