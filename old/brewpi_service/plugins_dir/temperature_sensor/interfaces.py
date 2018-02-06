from zope.interface import Interface, Attribute

class ISensor(Interface):
    """
    A mono-value sensor
    """
    sensor_value  = Attribute("""Actual value of this sensor""")


class ISensorSetpointPair(Interface):
    """
    A compound object of a setpoint and a sensor value
    """
    setpoint = Attribute("""The setpoint object""")
    sensor = Attribute("""The sensor object""")


class ISetpoint(Interface):
    """
    A Setpoint for a PID
    """
    value = Attribute("""Actual value of the setpoint""")


class IPID(Interface):
    """
    A proportional–integral–derivative controller (PID controller) is a control
    loop feedback mechanism (controller) commonly used in industrial control
    systems. A PID controller continuously calculates an error value e(t) as
    the difference between a desired setpoint and a measured process variable
    and applies a correction based on proportional, integral, and derivative
    terms (sometimes denoted P, I, and D respectively) which give their name to
    the controller type. -- wikipedia
    """
    enabled = Attribute("""If this PID is enabled""")
    kp = Attribute("""Proportional gain""")
    ti = Attribute("""Integral time constant""")
    td = Attribute("""Derivative time constant""")

    p = Attribute("""Proportional term value, read-only""")
    i = Attribute("""Integral term value, read-only""")
    d = Attribute("""Derivative term value, read-only""")

    actuator_is_negative = Attribute("""If the actuator is negative""")
    input_error = Attribute("""Input error, read-only""")

    set_point = Attribute("""The setpoint object associated with this PID""")
    input_sensor = Attribute("""The Input Sensor object associated with this PID""")
    output_actuator = Attribute("""The Output Actuator object associated with this PID""")
