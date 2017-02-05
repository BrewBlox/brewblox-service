from sqlalchemy import (
    Column, Integer, String,
    Boolean, ForeignKey
)

from brewpi_service.database import Base, ControllerData
from brewpi_service.controller.models import ControllerDevice


class TemperatureSensorDevice(ControllerDevice):
    """
    A DS2xxx Temperature Sensor
    """
    __tablename__ = 'temperature_sensor_device'

    __mapper_args__ = {
        'polymorphic_identity': "temperature_sensor_device"
    }
    id = Column(Integer, ForeignKey('controller_device.id'), primary_key=True)

    value = ControllerData(Integer)

    def __repr__(self):
        return '<Temperature Sensor {0} -> {1}>'.format(self.id, self.value)
