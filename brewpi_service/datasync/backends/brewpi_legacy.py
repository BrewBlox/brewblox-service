import logging
import platform
import time

from circuits import handler, Component

from brewpiv2.commands import ListInstalledDevicesCommand
from brewpiv2.controller import (
    BrewPiControllerManager,
    BrewPiController,
    ControllerObserver,
    MessageHandler
)

from brewpiv2.messages.decoder import RawMessageDecoder


from brewpi_service.controller.models import Controller
from brewpi_service.controller.events import (
    ControllerConnected,
    ControllerDisconnected
)

from ..abstract import AbstractControllerSyncherBackend


LOGGER = logging.getLogger(__name__)


class BrewPiLegacySyncherBackend(Component, AbstractControllerSyncherBackend):
    """
    A loop that syncs a BrewPi Controller using the legacy firmware
    """
    def __init__(self):
        super(BrewPiLegacySyncherBackend, self).__init__()

        self.manager = BrewPiControllerManager()
        self.msg_decoder = RawMessageDecoder()
        self.msg_handler = SyncherMessageHandler()

        self.controller_observer = BrewPiLegacyControllerObserver().register(self)

        self.shutdown = False

    @handler("stopped")
    def stopped(self, *args):
        print("STOPPPEED")
        self.shutdown = True

    @handler("started")
    def started(self, *args):
        wifi_ctrl = BrewPiController("socket://192.168.0.54:6666")
        self.manager.controllers[wifi_ctrl.serial_port] = wifi_ctrl
        wifi_ctrl.subscribe(self.controller_observer)
        wifi_ctrl.connect()


        while not self.shutdown:
            # Update manager
            for new_controller in self.manager.update():
                time.sleep(1)  # FIXME ugly
                new_controller.subscribe(self.controller_observer)
                new_controller.connect()

            # Process messages from controllers
            for port, controller in self.manager.controllers.items():
                if controller.is_connected:
                    # Read values of devices
                    controller.send(ListInstalledDevicesCommand(with_values=True))
                    time.sleep(1)

                    for raw_message in controller.process_messages():
                        for msg in self.msg_decoder.decode_controller_message(raw_message):
                            self.msg_handler.accept(msg)
                            LOGGER.debug(msg)

            time.sleep(0.5)


class SyncherMessageHandler(MessageHandler):
    """
    Take actions upon Controller Message reception
    """
    def installed_device(self, anInstalledDeviceMessage):
        LOGGER.warn("TBI: update installed device!")

    def available_device(self, anAvailableDeviceMessage):
        LOGGER.warn("TBI: update available device!")

    def uninstalled_device(self, anUninstalledDeviceMessage):
        LOGGER.warn("TBI: update uninstalled device!")

    def log_message(self, aLogMessage):
        LOGGER.warn("TBI: Log message !")

    def control_settings(self, aControlSettingsMessage):
        LOGGER.warn("TBI: Control Settings!")

    def control_constants(self, aControlConstantsMessage):
        LOGGER.warn("TBI: Control Constants!")

    def temperatures(self, aTemperaturesMessage):
        LOGGER.warn("TBI: Temperatures!")


class BrewPiLegacyControllerObserver(Component, ControllerObserver):
    """
    Controller event handler for the Legacy backend.

    Receives events from the backend and dispatch them as events the service
    can understand.
    """
    def _make_controller_uri(self, aBrewPiController):
        """
        Forge the controller uri as a string
        """
        return "{0}:{1}".format(platform.node(),
                                aBrewPiController.serial_port)

    def _on_controller_connected(self, aBrewPiController):
        controller = Controller(name="Serial BrewPi on {0} at {1}".format(platform.node(),
                                                                          aBrewPiController.serial_port),
                                uri=self._make_controller_uri(aBrewPiController),
                                description="A BrewPi connected to a serial port, using the legacy protocol.",
                                connected=aBrewPiController.is_connected)

        self.fire(ControllerConnected(controller))

    def _on_controller_disconnected(self, aBrewPiController):
        self.fire(ControllerDisconncted(Controller(uri=self._make_controller_uri(aBrewPiController))))
