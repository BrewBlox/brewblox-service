from brewpi_service import ma

from .models import TemperatureSensorDevice


class TemperatureSensorDeviceSchema(ma.ModelSchema):
    class Meta:
        model = TemperatureSensorDevice
        fields = ('id', 'value', 'url')

    url = ma.AbsoluteUrlFor('temperature_sensor_detail', id='<id>')


temperature_sensor_schema = TemperatureSensorDeviceSchema()
temperature_sensors_schema = TemperatureSensorDeviceSchema(many=True)
