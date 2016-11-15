from sqlalchemy import (
    Column, Integer, String,
    Boolean, ForeignKey
)

from brewpi_service.database import Base
from brewpi_service.controller.models import ControllerDevice


class ClockDevice(ControllerDevice):
    """
    A clock Sensor
    """
    __tablename__ = 'clock'

    time = Column(Integer)

    def __repr__(self):
        return '<Clock {0} -> {1}>'.format(self.name, self.time)
