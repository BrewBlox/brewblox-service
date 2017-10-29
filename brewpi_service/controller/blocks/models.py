from sqlalchemy import (
    Column, Integer, String, Boolean, ForeignKey,
    UniqueConstraint, DateTime
)
from zope.interface import implementer

from ..models import ControllerBlock

from .interfaces import ISwitchActuator


@implementer(ISwitchActuator)
class DigitalPin(ControllerBlock):
    is_inverted = Column(Boolean)
    pin_number = Integer()
