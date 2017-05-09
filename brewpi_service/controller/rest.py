from flask_apispec import MethodResource
from flask_apispec import marshal_with

from brewpi_service.rest import api_v1

from .models import Controller, ControllerBlock
from .schemas import (
    ControllerSchema,
    ControllerBlockSchema
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


@marshal_with(ControllerBlockSchema(many=True))
class ControllerBlockList(MethodResource):
    def get(self):
        return ControllerBlock.query.all()

api_v1.register('/controllers/blocks/', ControllerBlockList)
