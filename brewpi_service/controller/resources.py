from flask_restful import reqparse
from flask_restful import abort
from flask_restful import Resource
from flask_restful import fields
from flask_restful import marshal_with

from .models import Controller
from ..database import db_session

from brewpi_service.rest import api

controller_fields = {
    'id': fields.Integer,
    'name': fields.String,
    'uri': fields.Url('controllers_detail', absolute=True),
}

parser = reqparse.RequestParser()
parser.add_argument('controller', type=int)


class ControllerResource(Resource):
    """
    Resource for a Controller
    """
    @marshal_with(controller_fields)
    def get(self, id):
        controller = db_session.query(Controller).filter(Controller.id == id).first()
        if not controller:
            abort(404, message="Controller {} doesn't exist".format(id))
        return controller


class ControllerListResource(Resource):
    """
    List controllers
    """
    @marshal_with(controller_fields)
    def get(self):
        controllers = db_session.query(Controller).all()
        return controllers


# Add models to API
api.add_resource(ControllerResource, '/controller/<int:id>', endpoint='controllers_detail')
api.add_resource(ControllerListResource, '/controller', endpoint='controllers_list')
