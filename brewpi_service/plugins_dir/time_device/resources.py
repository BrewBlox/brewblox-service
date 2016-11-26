from flask_restful import reqparse
from flask_restful import abort
from flask_restful import Resource
from flask_restful import fields
from flask_restful import marshal_with

from brewpi_service.database import db_session

from .models import ClockDevice

clockdevice_fields = {
    'id': fields.Integer,
    '_scale': fields.Integer,
    'time': fields.Integer,
    'uri': fields.Url('clockdevice_detail', absolute=True),
}

parser = reqparse.RequestParser()
parser.add_argument('clockdevice', type=int)


class ClockDeviceResource(Resource):
    """
    Resource for a ClockDevice
    """
    @marshal_with(clockdevice_fields)
    def get(self, id):
        clock_device = db_session.query(ClockDevice).filter(ClockDevice.id == id).first()
        if not clock_device:
            abort(404, message="Clock Device {} doesn't exist".format(id))
        return clock_device
