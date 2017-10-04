from sqlalchemy import (
    Column, Integer, ForeignKey
)

from brewpi_service.controller.state import ControllerDataField
from brewpi_service.controller.models import ControllerBlock


class ClockDevice(ControllerBlock):
    """
    A clock Sensor
    """
    __tablename__ = 'clock_device'

    __mapper_args__ = {
        'polymorphic_identity': "clock_device"
    }
    id = Column(Integer, ForeignKey('controller_block.id'), primary_key=True)

    scale = ControllerDataField(Integer, writable=True)
    time = ControllerDataField(Integer)

    def __repr__(self):
        return '<Clock {0} -> {1} (x{2})>'.format(self.id, self.time, self.scale)
