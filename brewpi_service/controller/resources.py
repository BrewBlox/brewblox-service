from flask import jsonify

from flask_restful import reqparse
from flask_restful import abort
from flask_restful import Resource
from flask_restful import fields
from flask_restful import marshal_with

from brewpi_service import app
from brewpi_service.rest import api

from ..database import db_session

from .models import Controller, ControllerDevice
from .schemas import (
    controller_schema,
    controllers_schema,
    controller_device_schema,
    controller_devices_schema
)


@app.route('/controllers/')
def controllers():
    all_controllers = Controller.query.all()
    result = controllers_schema.dump(all_controllers)
    return jsonify(result.data)


@app.route('/controllers/devices/')
def controller_devices():
    all_devices = ControllerDevice.query.all()
    result = controller_devices_schema.dump(all_devices)
    return jsonify(result.data)

@app.route('/controllers/devices/<id>')
def controller_device_detail(id):
    device = ControllerDevice.query.get(id)
    return controller_device_schema.jsonify(device)


