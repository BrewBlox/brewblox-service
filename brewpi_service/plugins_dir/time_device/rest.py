from brewpi_service.rest import (
    marshal_with,
    MethodResource,
    api_v1
)

from .models import ClockDevice
from .schemas import ClockSchema


@marshal_with(ClockSchema(many=True))
class ClockList(MethodResource):
    """
    List Clocks
    """
    def get(self, **kwargs):
        return ClockDevice.query.all()

api_v1.register('/clocks/', ClockList)


@marshal_with(ClockSchema)
class ClockDetail(MethodResource):
    """
    Detail a given Clock
    """
    def get(self, id, **kwargs):
        return ClockDevice.query.get(id)

api_v1.register('/clocks/<id>/', ClockDetail)
