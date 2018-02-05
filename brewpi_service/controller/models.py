import datetime

from sqlalchemy import (
    Column, Integer, String, Boolean, ForeignKey,
    UniqueConstraint, DateTime
)
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declared_attr

from ..database import Base, db_session


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
        'with_polymorphic': '*'
    }


class ControllerBlock(BaseObject):
    """
    Any block (i.e. object) living in the controller
    """
    __tablename__ = "controller_block"
    __mapper_args__ = {
        'polymorphic_identity': "controller_block",
        'polymorphic_on': 'type',
        'with_polymorphic': '*'
    }

    def __setattr__(self, name, value):
        if name in self.__class__._controller_data_fields:
            attribute = getattr(self, name)
            if type(value) is tuple:
                attribute.set_actual_value(value[0])
                attribute.request_value(value[1])
            else:
                attribute.request_value(value)

            return value
        else:
            return super().__setattr__(name, value)


    def get_dirty_fields(self):
        dirty_fields = []
        for field in self.__class__._controller_data_fields:
            if getattr(self, field)[2] == True:
                dirty_fields.append(field)

        return dirty_fields


    def get_actual_value_of_field(self, field_name):
        if name in self.__class__._controller_data_fields:
            attribute = getattr(self, name)
            attribute.request_value(value)


    is_static = Column(Boolean, default=False, nullable=False, doc="whether the object is hardcoded on the controller or user-creatable")

    profile_id = Column(Integer, ForeignKey('controller_profile.id'), nullable=True)
    profile = relationship("models.ControllerProfile")

    object_id = Column(Integer, nullable=False)
    name = Column(String, nullable=True)

    __table_args__ = (
        UniqueConstraint('profile_id', 'object_id', name='_controller_object_uc'),
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
    connected = Column(Boolean)

    profile_id = Column(Integer, ForeignKey('controller_profile.id'))
    profile = relationship("ControllerProfile", back_populates="controllers")

    def __repr__(self):
        return '<Controller {0}@{1} using profile "{2}">'.format(self.name, self.uri, self.profile)


class ControllerProfile(Base):
    """
    A Profile for a Controller
    """
    __tablename__ = 'controller_profile'

    id = Column(Integer, primary_key=True)
    name = Column(String(64), index=True, unique=True)

    controllers = relationship("Controller", back_populates="profile")

    blocks = relationship("ControllerBlock", back_populates="profile")

    def get_block_by_name(self, name):
        return ControllerBlock.query.with_polymorphic('*').filter(ControllerBlock.name==name).one()

    def __repr__(self):
        return self.name
