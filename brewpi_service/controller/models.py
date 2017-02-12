import datetime

from sqlalchemy import (
    Column, Integer, String, Boolean, ForeignKey,
    UniqueConstraint, DateTime
)
from sqlalchemy.orm import relationship, backref
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.sql import func

from ..database import Base


class TimestampMixin:
    """
    Timestamp mixin for keeping track of creation time and update of objects
    """
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)


class BaseObject(Base, TimestampMixin):
    """
    Basic object either living inside or outside the electronic world
    """
    __abstract__ = True

    id = Column(Integer, primary_key=True)
    type = Column(String(50))


class Device(BaseObject):
    """
    An device not living on a controller, i.e. a manually triggered device.
    """
    __tablename__ = "device"
    __mapper_args__ = {
        'polymorphic_identity': "device",
        'polymorphic_on': 'type',
        'with_polymorphic':'*'
    }


class ControllerObject(BaseObject):
    """
    Any object living in the controller
    """
    __tablename__ = "controller_object"
    __mapper_args__ = {
        'polymorphic_identity': "controller_object",
        'polymorphic_on': 'type',
        'with_polymorphic':'*'
    }

    @declared_attr
    def controller_id(self):
        return Column(Integer, ForeignKey('controller.id'), nullable=False)

    object_id = Column(Integer, nullable=False)

    __table_args__ = (
        UniqueConstraint('controller_id', 'object_id', name='_controller_object_uc'),
    )


class ControllerDevice(ControllerObject):
    """
    Any device tied to a controller, i.e. electronic or virtual
    """
    __tablename__ = "controller_device"

    __mapper_args__ = {
        'polymorphic_identity': "controller_device"
    }

    id = Column(Integer, ForeignKey('controller_object.id'), primary_key=True)


class ControllerLoop(ControllerObject):
    """
    A logical control block such as a PID
    """
    __tablename__ = "controller_loop"

    __mapper_args__ = {
        'polymorphic_identity': "controller_loop"
    }

    id = Column(Integer, ForeignKey('controller_object.id'), primary_key=True)


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

    devices = relationship("models.ControllerDevice", backref="controller")
    loops = relationship("models.ControllerLoop", backref="controller")

    def __repr__(self):
        return '<Controller {0} - {1}>'.format(self.name, self.uri)

