from flask import jsonify

from brewpi_service import app

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


@app.route('/controllers/<id>')
def controller_detail(id):
    device = Controller.query.get(id)
    return controller_schema.jsonify(device)


@app.route('/controllers/devices/')
def controller_devices():
    all_devices = ControllerDevice.query.all()
    result = controller_devices_schema.dump(all_devices)
    return jsonify(result.data)


@app.route('/controllers/devices/<id>')
def controller_device_detail(id):
    device = ControllerDevice.query.get(id)
    return controller_device_schema.jsonify(device)
