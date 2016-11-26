from sqlalchemy import (
    Column, Integer, String,
    Boolean, ForeignKey
)

from brewpi_service.database import Base, ControllerData
from brewpi_service.controller.models import ControllerDevice


class ClockDevice(ControllerDevice):
    """
    A clock Sensor
    """
    __tablename__ = 'clock'

    scale = ControllerData(Integer, writable=True)
    time = ControllerData(Integer)

    def __repr__(self):
        return '<Clock {0} -> {1}>'.format(self.name, self.time)
