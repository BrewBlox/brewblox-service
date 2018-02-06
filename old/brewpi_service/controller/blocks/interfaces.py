from zope.interface import Interface, Attribute

from ..interfaces import IBlock


class ISwitchActuator(IBlock):
    """
    Anything that can switch a state
    """
    is_inverted = Attribute("Is this pin inverted?")
