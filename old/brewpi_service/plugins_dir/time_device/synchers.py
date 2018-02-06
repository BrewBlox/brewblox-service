import logging

from brewpi_service.datasync.abstract import AbstractDeviceSyncher
from brewpi_service.database import db_session, get_or_create

from .models import ClockDevice

LOGGER = logging.getLogger("rq.worker")


class ScaledTimeSyncher(AbstractDeviceSyncher):
    """
    Handle synching with controller for device ClockDevice
    """
    def update(self, controller, state, event):
        LOGGER.debug(controller.system_id().read())
        device_id = int.from_bytes(event.idchain, byteorder="little", signed=False)

        # get or create model
        device, created = get_or_create(db_session, ClockDevice,
                                        create_method_kwargs={'time': state.time,
                                                              '_scale': state.scale},
                                        device_id=device_id,
                                        controller_id=1)

        if created is False:
            db_session.add(device)
            device.time = state.time
            device._scale = state.scale
            db_session.commit()
        else:
            LOGGER.info("Created <ClockDevice>(ID={0})".format(device_id))
