from sqlalchemy import (
    Column, Integer, String,
    Boolean, ForeignKey,
)
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.orm import relationship

from brewpi_service.database import Base, ControllerData
from brewpi_service.controller.models import ControllerDevice, ControllerLoop


class TemperatureSensorDevice(ControllerDevice):
    """
    A DS2xxx Temperature Sensor
    """
    __tablename__ = 'temperature_sensor_device'

    __mapper_args__ = {
        'polymorphic_identity': "temperature_sensor_device"
    }
    id = Column(Integer, ForeignKey('controller_device.id'), primary_key=True)

    value = ControllerData(Integer)

    def __repr__(self):
        return '<Temperature Sensor {0} -> {1}>'.format(self.id, self.value)


class PID(ControllerLoop):
    """
    A proportional–integral–derivative controller (PID controller) is a control
    loop feedback mechanism (controller) commonly used in industrial control
    systems.
    """
    __tablename__ = 'controller_loop_pid'

    __mapper_args__ = {
        'polymorphic_identity': "controller_loop_pid"
    }


    id = Column(Integer, ForeignKey('controller_loop.id'), primary_key=True)

    setpoint_id = Column(Integer, ForeignKey('controller_object.id'), nullable=True)
    setpoint = relationship('ControllerObject', backref='pid_setpoints', foreign_keys=[setpoint_id])


    actuator_id = Column(Integer, ForeignKey('controller_object.id'), nullable=True)
    actuator = relationship('ControllerObject', backref='pid_actuators', foreign_keys=[actuator_id])


    input_id = Column(Integer, ForeignKey('controller_object.id'), nullable=True)
    input = relationship('ControllerObject', backref='pid_inputs', foreign_keys=[input_id])


    def __repr__(self):
        return '<PID {0}:{1}>'.format(self.controller_id, self.object_id)


