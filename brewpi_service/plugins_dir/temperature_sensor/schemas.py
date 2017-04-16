from brewpi_service import ma

from .models import TemperatureSensorDevice, PID


class TemperatureSensorDeviceSchema(ma.ModelSchema):
    """
    Serialization schema for the TemperatureSensorDevice
    """
    class Meta:
        model = TemperatureSensorDevice
        fields = ('id', 'value', 'url')

    url = ma.AbsoluteUrlFor('temperature_sensor_detail', id='<id>')


temperature_sensor_schema = TemperatureSensorDeviceSchema()
temperature_sensors_schema = TemperatureSensorDeviceSchema(many=True)


class PIDLoopSchema(ma.ModelSchema):
    """
    Serialization schema for the PID Loop algorithm
    """
    class Meta:
        model = PID
        fields = ('id', 'input', 'actuator', 'setpoint', 'url')

    url = ma.AbsoluteUrlFor('pid_loop_detail', id='<id>')


pid_loop_schema = PIDLoopSchema()
pid_loops_schema = PIDLoopSchema(many=True)
