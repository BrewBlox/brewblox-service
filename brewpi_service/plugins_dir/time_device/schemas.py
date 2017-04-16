from brewpi_service import ma

from .models import ClockDevice


class ClockSchema(ma.ModelSchema):
    class Meta:
        model = ClockDevice
        fields = ('id', 'scale', 'time', 'url')

    scale = ma.Integer(attribute='_scale')
    url = ma.AbsoluteUrlFor('clock_detail', id='<id>')


clock_schema = ClockSchema()
clocks_schema = ClockSchema(many=True)
