from sqlalchemy import (
    Column, Integer, ForeignKey
)

from brewpi_service.database import ControllerData
from brewpi_service.controller.models import ControllerDevice


class ClockDevice(ControllerDevice):
    """
    A clock Sensor
    """
    __tablename__ = 'clock_device'

    __mapper_args__ = {
        'polymorphic_identity': "clock_device"
    }
    id = Column(Integer, ForeignKey('controller_device.id'), primary_key=True)

    scale = ControllerData(Integer, writable=True)
    time = ControllerData(Integer)

    def __repr__(self):
        return '<Clock {0} -> {1} (x{2})>'.format(self.id, self.time, self.scale)
