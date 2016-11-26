from sqlalchemy import (
    Column, Integer, String, Boolean, ForeignKey,
    UniqueConstraint
)
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declared_attr

from ..database import Base


class Device(Base):
    """
    A device that can do or sense something
    """
    __abstract__ = True

    id = Column(Integer, primary_key=True)
    type = Column(String(50))

    __mapper_args__ = {
        'polymorphic_identity': 'device',
        'polymorphic_on': type
    }


class ControllerDevice(Device):
    """
    Any device tied to a controller, i.e. electronic or virtual
    """
    __tablename__ = "controller_device"
    __mapper_args__ = {
        'polymorphic_identity': "controller_device"
    }

    @declared_attr
    def controller_id(self):
        return Column(Integer, ForeignKey('controller.id'), nullable=False)

    device_id = Column(Integer, nullable=False)

    __table_args__ = (
        UniqueConstraint('controller_id', 'device_id', name='_controller_device_uc'),
    )

class Controller(Base):
    """
    A Hardware Controller that holds sensors and actuators
    """
    __tablename__ = 'controller'

    id = Column(Integer, primary_key=True)
    name = Column(String(64), index=True, unique=True)
    uri = Column(String(128), index=True, unique=True)
    description = Column(String(128))
    alive = Column(Boolean)

    devices = relationship("ControllerDevice")

    def __repr__(self):
        return '<Controller {0} - {1}>'.format(self.name, self.uri)

