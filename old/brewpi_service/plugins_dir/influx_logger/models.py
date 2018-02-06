from sqlalchemy import (
    Column, Integer,
    String, ForeignKey
)
from sqlalchemy.orm import relationship, backref

from brewpi_service.database import Base
from brewpi_service.controller.models import ControllerBlock


class LoggedDeviceConfiguration(Base):
    """
    Configurable Watched Devices so they are logged into influxdb
    """
    __tablename__ = 'influx_logged_devices'

    id = Column(Integer, primary_key=True)

    block_id = Column(Integer, ForeignKey('controller_block.id'), nullable=False)
    block = relationship(ControllerBlock,
                         backref=backref('logging_configurations',
                                         uselist=True,
                                         cascade='delete, all'))

    device_field = Column(String, nullable=False)

    def __repr__(self):
        return '<Device logging configuration for {0})>'.format(self.device)
