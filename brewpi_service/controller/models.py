from sqlalchemy import (
    Column, Integer, String, Boolean, ForeignKey
)

from ..database import Base


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

    def __repr__(self):
        return '<Controller {0} - {1}>'.format(self.name, self.uri)


class Device(Base):
    """
    A device that can do or sense something
    """
    id = Column(Integer, primary_key=True)
    type = Column(String(50))

    __mapper_args__ = {
        'polymorphic_identity': 'device',
        'polymorphic_on':type
    }

class ControllerDevice(Device):
    """
    Any device tied to a controller, i.e. electronic or virtual
    """
    controller_id = Column(Integer, ForeignKey('controller.id'))

