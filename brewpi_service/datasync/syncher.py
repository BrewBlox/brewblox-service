import logging
import os
import stat
from threading import Thread

from basicevents import run as events_run


import Pyro4 as pyro

from .backends.brewpi_legacy import BrewPiLegacySyncherBackend
from .backstores.database import DatabaseSyncher
from .forwarders.sse import SSEForwarder

LOGGER = logging.getLogger(__name__)


@pyro.behavior(instance_mode="single")
class DataSyncherServer:
    """
    Main synching process that spawns hardware backends and triggers backstores
    on events.
    """
    def __init__(self, unix_socket_name="brewpi-service-syncher"):
        self._backstores = (DatabaseSyncher())
        self._forwarders = (SSEForwarder())
        self._backends = (BrewPiLegacySyncherBackend(),)
        self._threads = []
        self._unix_socket_name = unix_socket_name

    def run(self):
        # Run the even system
        events_run()

        # Build backend threads
        for backend in self._backends:
            backend_thread = Thread(target=backend.run, name=backend.__class__.__name__)
            self._threads.append(backend_thread)

        # Run them
        for thread in self._threads:
            thread.start()

        # Remove stale socket if necessary
        try:
            if stat.S_ISSOCK(os.stat(self._unix_socket_name).st_mode):
                os.remove(self._unix_socket_name)
        except FileNotFoundError:
            pass

        # Start a pyro server
        server = pyro.Daemon(unixsocket=self._unix_socket_name)

        syncher_uri = server.register(self, objectId="syncher")
        LOGGER.debug("Registered syncher as {0}".format(syncher_uri))

        server.requestLoop()

    @pyro.expose
    def blah(self):
        self.cb()
        return [[controller[0] for controller in backend.manager.controllers.items()] for backend in self._backends]



