import coloredlogs
import logging

from brewpi_service.datasync import DataSyncherServer

coloredlogs.install(level='DEBUG')

from circuits import Debugger, Component, handler

from brewpi_service import app

LOGGER = logging.getLogger(__name__)

class RestWebServer(Component):
    def __init__(self):
        super(RestWebServer, self).__init__()
        self.app = app

    @handler("started")
    def started(self, *args):
        LOGGER.info("Running Web server...")
        self.app.run()

class Service(Component):
    def init(self):
        self._components = (DataSyncherServer().register(self),
                            RestWebServer().start(process=False, link=self))

service = Service()

Debugger().register(service)

service.run()
