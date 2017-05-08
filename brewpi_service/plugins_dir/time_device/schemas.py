from brewpi_service import ma
from brewpi_service.controller.schemas import ControllerDeviceSchema

from .models import ClockDevice


class ClockSchema(ControllerDeviceSchema):
    """
    A clock that ticks
    """
    class Meta:
        model = ClockDevice
        fields = ('id', 'scale', 'time', 'url')

    scale = ma.Integer(attribute='_scale')
    url = ma.AbsoluteUrlFor('clockdevice.details_view', id='<id>')
