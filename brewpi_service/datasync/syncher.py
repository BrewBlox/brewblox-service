import logging
import os
import stat
from threading import Thread

from .backends.brewpi_legacy import BrewPiLegacySyncherBackend
from .backends.mock import VirtualBrewPiSyncherBackend
from .backstores.database import DatabaseSyncher
from .forwarders.sse import SSEForwarder

LOGGER = logging.getLogger(__name__)

from circuits import Component, handler
from brewpi_service.controller.events import ControllerRequestCurrentProfile

from brewpi_service.controller.state import ControllerStateManager


class DataSyncherServer(Component):
    """
    Main synching process that spawns hardware backends in threadsand triggers
    backstores on events.
    """
    def init(self):
        self._state_manager = ControllerStateManager().register(self)

        self._backstores = (DatabaseSyncher().register(self))
        self._forwarders = (SSEForwarder().register(self))
        self._backends = (VirtualBrewPiSyncherBackend(self._state_manager).register(self))
        # self._backends = (BrewPiLegacySyncherBackend(self._state_manager).register(self))


    @handler("started")
    def started(self, *args):
        LOGGER.info("Data Syncher running...")
