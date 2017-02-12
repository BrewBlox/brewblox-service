from sqlalchemy import (
    Column, Integer, String,
    Boolean, ForeignKey,
)
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.orm import relationship, backref

from brewpi_service.database import Base
from brewpi_service.controller.models import ControllerObject


class LoggedDeviceConfiguration(Base):
    """
    Configurable Watched Devices so they are logged into influxdb
    """
    __tablename__ = 'influx_logged_devices'

    id = Column(Integer, primary_key=True)

    device_id = Column(Integer, ForeignKey('controller_object.id'), nullable=False)
    device = relationship(ControllerObject,
                          backref=backref('logging_configurations',
                                          uselist=True,
                                          cascade='delete, all'))

    device_field = Column(String, nullable=False)

    def __repr__(self):
        return '<Device logging configuration for {0})>'.format(self.device)
