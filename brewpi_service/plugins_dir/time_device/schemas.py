from brewpi_service import ma

from .models import ClockDevice


class ClockSchema(ma.ModelSchema):
    class Meta:
        model = ClockDevice
        fields = ('id', '_scale', 'time', 'url')

    url = ma.AbsoluteUrlFor('clock_detail', id='<id>')



clock_schema = ClockSchema()
clocks_schema = ClockSchema(many=True)
