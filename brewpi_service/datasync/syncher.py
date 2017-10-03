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


class DataSyncherServer(Component):
    """
    Main synching process that spawns hardware backends in threadsand triggers
    backstores on events.
    """
    def __init__(self):
        super(DataSyncherServer, self).__init__()
        self._backstores = (DatabaseSyncher().register(self))
        self._forwarders = (SSEForwarder().register(self))
        self._backends = (VirtualBrewPiSyncherBackend().register(self))

    @handler("started")
    def started(self, *args):
        LOGGER.info("Data Syncher running...")
