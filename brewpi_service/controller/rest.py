from werkzeug.exceptions import NotFound

from flask_apispec import MethodResource
from flask_apispec import marshal_with

from brewpi_service.rest import api_v1
from brewpi_service.datasync.backends.cache import available_blocks_cache

from .models import Controller, ControllerBlock, ControllerProfile
from .schemas import (
    ControllerSchema,
    ControllerBlockSchema,
    ControllerAvailableBlockSchema,
    ControllerProfileSchema
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


@marshal_with(ControllerAvailableBlockSchema(many=True))
class ControllerAvailableBlockList(MethodResource):
    """
    Available Blocks from the Controller
    """
    def get(self, controller_id):
        controller = Controller.query.get(controller_id)
        if controller is None:
            raise NotFound()
        return available_blocks_cache.get_all_for(controller)

api_v1.register('/controllers/<controller_id>/available_blocks/', ControllerAvailableBlockList)


@marshal_with(ControllerProfileSchema)
class ControllerProfileDetail(MethodResource):
    def get(self, id):
        return ControllerProfile.query.get(id)

api_v1.register('/controller_profiles/<id>/', ControllerProfileDetail)


@marshal_with(ControllerBlockSchema(many=True))
class ControllerBlockList(MethodResource):
    def get(self):
        return ControllerBlock.query.all()

api_v1.register('/controller_blocks/', ControllerBlockList)


@marshal_with(ControllerBlockSchema)
class ControllerBlockDetail(MethodResource):
    def get(self, id):
        return ControllerBlock.query.get(id)

api_v1.register('/controller_blocks/<id>/', ControllerBlockDetail)
