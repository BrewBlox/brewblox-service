import logging
import platform
import time

from basicevents import send

from brewpiv2.controller import (
    BrewPiControllerManager,
    ControllerObserver
)

from brewpiv2.messages.decoder import RawMessageDecoder

from brewpi_service.controller.models import Controller

from ..abstract import AbstractControllerSyncherBackend


LOGGER = logging.getLogger(__name__)


class BrewPiLegacySyncherBackend(AbstractControllerSyncherBackend):
    """
    A loop that syncs a BrewPi Controller using the legacy firmware
    """
    def __init__(self):
        self.manager = BrewPiControllerManager()
        self.msg_decoder = RawMessageDecoder()

        self.controller_observer = BrewPiLegacyControllerObserver()

    def run(self):
        while True:
            # Update manager
            for new_controller in self.manager.update():
                time.sleep(1)  # FIXME ugly
                new_controller.subscribe(self.controller_observer)
                new_controller.connect()

            # Process messages from controllers
            for port, controller in self.manager.controllers.items():
                if controller.is_connected:
                    for raw_message in controller.process_messages():
                        for msg in self.msg_decoder.decode_controller_message(raw_message):
                            LOGGER.debug(msg)

            time.sleep(0.05)


class BrewPiLegacyControllerObserver(ControllerObserver):
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

        send("controller.connected", aController=controller)

    def _on_controller_disconnected(self, aBrewPiController):
        send("controller.disconnected", aController=Controller(uri=self._make_controller_uri(aBrewPiController)))


