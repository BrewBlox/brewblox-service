from sqlalchemy import (
    Column, Integer, String, Boolean, ForeignKey,
    UniqueConstraint, DateTime
)
from zope.interface import implementer

from ..models import ControllerBlock

from .interfaces import ISwitchActuator


@implementer(ISwitchActuator)
class DigitalPin(ControllerBlock):
    __tablename__ = 'controller_block_digital_pin'

    __mapper_args__ = {
        'polymorphic_identity': "controller_block_digital_pin"
    }

    digital_pin_id = Column(Integer, ForeignKey('controller_block.id', ondelete="CASCADE"), primary_key=True)

    is_inverted = Column(Boolean)
    pin_number = Integer()

    def __repr__(self):
        return "<DigitalPin '{0}'>".format(self.name)
