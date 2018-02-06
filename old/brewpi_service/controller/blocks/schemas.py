from brewpi_service import ma

from zope.interface import implementer

from ..schemas import ControllerBlockDisambiguator, ControllerBlockSchema

from .interfaces import ISwitchActuator

from .models import DigitalPin


@implementer(ISwitchActuator)
class DigitalPinSchema(ControllerBlockSchema):
    """
    Serialization schema for a Digital Pin
    """
    class Meta:
        model = DigitalPin
        fields = ControllerBlockSchema.Meta.fields


ControllerBlockDisambiguator.class_to_schema[DigitalPin.__name__] = DigitalPinSchema
