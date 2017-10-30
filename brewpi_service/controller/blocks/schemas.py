from zope.interface import implementer

from .interfaces import ISwitchActuator

from .models import DigitalPin


@implementer(ISwitchActuator)
class DigitalPinSchema(ControllerBlockSchema):
    """
    Serialization schema for a Digital Pin
    """
    class Meta:
        model = DigitalPin
        fields = ('id', 'name', 'url')

    url = ma.AbsoluteUrlFor('digital_pin.details_view', id='<id>')
