from sqlalchemy import (
    Column, Integer, String, Float, ForeignKey
)
from sqlalchemy.orm import relationship, backref


from brewpi_service.controller.models import ControllerBlock, BaseObject

from brewpi_service.controller.state import ControllerData, VolatileStateMeta

from zope.interface import implementer

from .interfaces import (
    IProcessValue, ISensor
)

class ProcessValueMixin(BaseObject):
    __tablename__ = 'process_value_mixin'

    __mapper_args_ = {
        'polymorphic_identity': 'process_value_mixin'
    }


@implementer(IProcessValue)
class SensorSetpointPair(ControllerBlock, ProcessValueMixin):
    """
    A Simple pair of a sensor and a setpoint
    """
    __tablename__ = 'controller_block_sensor_setpoint_pair'

    __mapper_args__ = {
        'polymorphic_identity': "controller_block_sensor_setpoint_pair"
    }


    sensor_setpoint_pair_id = Column(Integer, ForeignKey('controller_block.id'), primary_key=True)

    name = Column(String, nullable=True)
    # value = ControllerData(Float)
    value = ControllerData(Float)


@implementer(ISensor)
class TemperatureSensor(ControllerBlock):
    """
    A DS2xxx Temperature Sensor
    """
    __tablename__ = 'controller_block_ds2xxx_sensor'

    __mapper_args__ = {
        'polymorphic_identity': "controller_block_ds2xxx_sensor"
    }
    ds2xxx_sensor_id = Column(Integer, ForeignKey('controller_block.id'), primary_key=True)

    # value = ControllerData(Integer)

    def __repr__(self):
        return '<Temperature Sensor {0} -> {1}>'.format(self.ds2xxx_sensor_id, self.value)


class PID(ControllerBlock):
    """
    A proportional–integral–derivative controller (PID controller) is a control
    loop feedback mechanism (controller) commonly used in industrial control
    systems.
    """
    __tablename__ = 'controller_block_pid'

    id = Column(Integer, ForeignKey('controller_block.id'), primary_key=True)

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
    input = relationship('ControllerBlock',
                         foreign_keys=[input_id],
                         primaryjoin="ControllerBlock.id == PID.input_id",
                         backref=backref('pid_inputs',
                                         remote_side="ControllerBlock.id"))

    kp = ControllerData(Float, writable=True)


    def __repr__(self):
        return '<PID {0}:{1}>'.format(self.profile, self.object_id)
