from flask import jsonify

from flask_restful import reqparse
from flask_restful import abort
from flask_restful import Resource
from flask_restful import fields
from flask_restful import marshal_with

from brewpi_service import app

from .models import TemperatureSensorDevice
from .schemas import (
    temperature_sensor_schema,
    temperature_sensors_schema
)


@app.route('/temperature_sensors/')
def temperature_sensors():
    """
    List Temperature Sensors
    """
    all_sensors = TemperatureSensorDevice.query.all()
    result = temperature_sensors_schema.dump(all_sensors)
    return jsonify(result.data)

@app.route('/temperature_sensors/<id>')
def temperature_sensor_detail(id):
    """
    Detail a given Temperature Sensor Device
    """
    temperature_sensor = TemperatureSensorDevice.query.get(id)
    return temperature_sensor_schema.jsonify(temperature_sensor)
