from sqlalchemy import (
    Column, Integer, String, Float, ForeignKey
)
from sqlalchemy.orm import relationship, backref


from brewpi_service.controller.models import ControllerBlock, BaseObject

from brewpi_service.controller.state import ControllerDataField

from zope.interface import implementer

from .interfaces import (
    ISetpoint,
    ISensorSetpointPair,
    ISensor
)

class ProcessValueMixin(BaseObject):
    __tablename__ = 'process_value_mixin'

    __mapper_args_ = {
        'polymorphic_identity': 'process_value_mixin'
    }


@implementer(ISetpoint)
class SetpointSimple(ControllerBlock):
    """
    A Simple Setpoint
    """
    __tablename__ = 'controller_block_setpoint_simple'

    __mapper_args__ = {
        'polymorphic_identity': "controller_block_setpoint_simple"
    }

    simple_setpoint_id = Column(Integer, ForeignKey('controller_block.id', ondelete='CASCADE'), primary_key=True)

    name = Column(String, nullable=True)

    value = ControllerDataField(Float)

    def __repr__(self):
        return "<SetpointSimple '{0}':{1}>".format(self.name,
                                                  self.value)


@implementer(ISensorSetpointPair)
class SensorSetpointPair(ControllerBlock):
    """
    A Simple pair of a sensor and a setpoint
    """
    __tablename__ = 'controller_block_sensor_setpoint_pair'

    __mapper_args__ = {
        'polymorphic_identity': "controller_block_sensor_setpoint_pair"
    }

    # sensor_setpoint_pair_id = Column(Integer, ForeignKey('controller_block.id'), primary_key=True)

    setpoint_id = Column(Integer, ForeignKey('controller_block.id'), nullable=True)
    setpoint = relationship("ControllerBlock", primaryjoin="and_(SensorSetpointPair.setpoint_id==ControllerBlock.id)", backref="setpoint_setpoint_pair")

    # sensor_id = Column(Integer, ForeignKey('controller_block.id'))
    # sensor = relationship("ControllerBlock", primaryjoin="and_(SensorSetpointPair.sensor_id==ControllerBlock.id)", backref="sensor_setpoint_pair")

    def __repr__(self):
        return '<SetPointPair set:{0}>'.format(self.setpoint)



@implementer(ISensor)
class TemperatureSensor(ControllerBlock):
    """
    A DS2xxx Temperature Sensor
    """
    __tablename__ = 'controller_block_ds2xxx_sensor'

    __mapper_args__ = {
        'polymorphic_identity': "controller_block_ds2xxx_sensor"
    }
    ds2xxx_sensor_id = Column(Integer, ForeignKey('controller_block.id', ondelete="CASCADE"), primary_key=True)

    value = ControllerDataField(Float)

    def __repr__(self):
        return "<Temperature Sensor '{0} at {1}°C'>".format(self.name, self.value)


class PID(ControllerBlock):
    """
    A proportional–integral–derivative controller (PID controller) is a control
    loop feedback mechanism (controller) commonly used in industrial control
    systems.
    """
    __tablename__ = 'controller_block_pid'

    id = Column(Integer, ForeignKey('controller_block.id', ondelete='CASCADE'), primary_key=True)

    __mapper_args__ = {
        'polymorphic_identity': "controller_block_pid",
        'inherit_condition': ControllerBlock.id == id
    }


    setpoint_id = Column(Integer, ForeignKey(ControllerBlock.id), nullable=True)
    setpoint = relationship('ControllerBlock',
                            primaryjoin="ControllerBlock.id == PID.setpoint_id",
                            foreign_keys=[setpoint_id],
                            backref=backref('pid_setpoints',
                                            remote_side="ControllerBlock.id"))

    actuator_id = Column(Integer, ForeignKey(ControllerBlock.id), nullable=True)
    actuator = relationship('ControllerBlock',
                            primaryjoin="ControllerBlock.id == PID.actuator_id",
                            foreign_keys=[actuator_id],
                            backref=backref('pid_actuators',
                                            remote_side="ControllerBlock.id"))

    input_id = Column(Integer, ForeignKey(ControllerBlock.id), nullable=True)
    input = ControllerDataField(relationship('ControllerBlock',
                                             foreign_keys=[input_id],
                                             primaryjoin="ControllerBlock.id == PID.input_id",
                                             backref=backref('pid_inputs',
                                                             remote_side="ControllerBlock.id")), writable=True)

    kp = ControllerDataField(Float, writable=True)


    def __repr__(self):
        return '<PID {0}:{1}>'.format(self.profile, self.object_id)
