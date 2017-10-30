import logging
import platform
import time
from datetime import datetime, timedelta

from circuits import handler, Component

from brewpiv2.commands import (
    ControlSettingsCommand,
    ListInstalledDevicesCommand,
    ListAvailableDevicesCommand
)
from brewpiv2.constants import (
    HardwareType
)
from brewpiv2.controller import (
    BrewPiControllerManager,
    BrewPiController,
    ControllerObserver,
    MessageHandler,
    message_received
)

from brewpi_service.database import db_session

from brewpiv2.messages.decoder import RawMessageDecoder

from brewpi_service.controller.profile import ControllerProfileManager, NoResultFound

from brewpi_service.controller.models import Controller
from brewpi_service.controller.events import (
    ControllerConnected,
    ControllerDisconnected,
    ControllerBlockList
)
from brewpi_service.controller.profile import (
    ControllerProfileManager,
    NoResultFound
)
from brewpi_service.controller.state import ControllerStateManager
from brewpi_service.controller.blocks.models import DigitalPin

from brewpi_service.plugins_dir.temperature_sensor.models import TemperatureSensor, PID, SensorSetpointPair, SetpointSimple


from ..abstract import AbstractControllerSyncherBackend


LOGGER = logging.getLogger(__name__)


class BrewPiLegacySyncherBackend(Component, AbstractControllerSyncherBackend):
    """
    A loop that syncs a BrewPi Controller using the legacy firmware
    """
    def __init__(self, aControllerStateManager):
        super(BrewPiLegacySyncherBackend, self).__init__()

        self.manager = BrewPiControllerManager()
        self.msg_decoder = RawMessageDecoder()


        self.controller_state = None
        self._controller_state_manager = aControllerStateManager

        self.shutdown = False

    @staticmethod
    def make_profile(name="brewpiv2"):
        """
        Create the brewpiv2 profile
        """
        LOGGER.info("Making BrewPi v2 Profile into database under name '{0}'...".format(name))
        profile = ControllerProfileManager.create(name, static=True)

        beer2_sensor = TemperatureSensor(profile=profile,
                                         object_id=49,
                                         name="beer2")

        db_session.add(beer2_sensor)

        beer2_setpoint = SetpointSimple(profile=profile,
                                        object_id=51,
                                        name="beer2set")
        db_session.add(beer2_setpoint)

        beer2_setpoint_pair = SensorSetpointPair(profile=profile,
                                                 setpoint=beer2_setpoint,
                                                 # sensor=beer2_sensor,
                                                 object_id=50) # not required since static

        db_session.add(beer2_setpoint_pair)

        # heater2_pwm = ActuatorPwm(profile=profile,
        #                           object_id=53,
        #                           period=4,
        #                           name="heater2pwm")

        # db_session.add(heater2_pwm)

        heater2_pid = PID(profile=profile,
                          name="heater2pid",
                          object_id=52,
                          input=beer2_setpoint_pair)
                          # output=heater2_pwm)

        db_session.add(heater2_pid)

        db_session.commit()

        return profile


    @handler("stopped")
    def stopped(self, *args):
        print("STOPPPEED")
        self.shutdown = True

    @handler("started")
    def started(self, *args):
        # Make sure we have our profile
        profile_name = "brewpiv2"
        try:
            self.profile = ControllerProfileManager.get(profile_name)
        except NoResultFound:
            self.profile = self.make_profile(name=profile_name)


        wifi_ctrl = BrewPiController("socket://192.168.1.6:6666")
        self.manager.controllers[wifi_ctrl.serial_port] = wifi_ctrl
        controller_observer = BrewPiLegacyControllerObserver(wifi_ctrl,
                                                             self.profile,
                                                             self._controller_state_manager).register(self)
        wifi_ctrl.subscribe(controller_observer)
        wifi_ctrl.connect()

        last_update = datetime.now()

        while not self.shutdown:
            while (datetime.now() - last_update) < timedelta(seconds=2):
                yield

            LOGGER.debug("Requesting update from backend {0}".format(self))
            # Update manager
            for new_controller in self.manager.update():
                controller_observer = BrewPiLegacyControllerObserver(new_controller,
                                                                     self.profile,
                                                                     self._controller_state_manager).register(self)

                new_controller.subscribe(controller_observer)
                new_controller.connect()

            # Process messages from controllers
            for port, controller in self.manager.controllers.items():
                if controller.is_connected:

                    # Request list of available devices with values
                    controller.send(ListAvailableDevicesCommand(with_values=True))

                    for raw_message in controller.process_messages():
                        for msg in self.msg_decoder.decode_controller_message(raw_message):
                            controller.notify(message_received, msg)

                            # LOGGER.debug(msg)

            last_update = datetime.now()



    def __str__(self):
        return "BrewPi Legacy Backend"


class SyncherMessageHandler(MessageHandler):
    """
    Take actions upon Controller Message reception
    """
    def __init__(self, aControllerProfile):
        self.updated_blocks = []
        self.controller_profile = aControllerProfile

    def clear_updates(self):
        """
        Once updates have been treated, clear them for next update
        """
        self.updated_blocks = []

    def installed_device(self, anInstalledDeviceMessage):
        LOGGER.warn("TBI: update installed device!")

    def available_device(self, aDevice):
        if aDevice.hardware_type == HardwareType.DIGITAL_PIN:
            self.updated_blocks.append(DigitalPin(profile=self.controller_profile,
                                                  profile_id=self.controller_profile.id,
                                                  name="Digital Pin {0}".format(aDevice.pin),
                                                  pin_number=aDevice.pin,
                                                  is_inverted=aDevice.pin_inverted))

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
    def __init__(self, aController, aControllerProfile, aControllerStateManager):
        super(BrewPiLegacyControllerObserver, self).__init__()

        self.controller_device = aController
        self.controller = None
        self.profile = aControllerProfile
        self.controller_state_manager = aControllerStateManager

        self.msg_handler = SyncherMessageHandler(self.profile)

    def _make_controller_uri(self, aBrewPiController):
        """
        Forge the controller uri as a string
        """
        return "{0}:{1}".format(platform.node(),
                                aBrewPiController.serial_port)



    @handler("ControllerStateChangeRequest")
    def on_controller_state_change_request(self, event):
        for change in event.changes:
            (block, fieldname, requested_value) = change
            if type(block) == PID:
                ## FIXME SPECIFIC
                print("post changes to controller {0} with {1} {2} {3}".format(self.controller, block, fieldname, requested_value))
                self.controller_device.send(ControlSettingsCommand(heater1_kp=requested_value))


    def _on_message_received(self, aMessage):
        """
        When a message is received from the controller
        """
        self.msg_handler.accept(aMessage)

        self.fire(ControllerBlockList(self.controller, self.msg_handler.updated_blocks))

        self.msg_handler.clear_updates()

    def _on_controller_connected(self, aBrewPiController):
        controller = Controller(name="BrewPi with legacy firmware on {0} at {1}".format(platform.node(),
                                                                                        aBrewPiController.serial_port),
                                profile=self.profile,
                                uri=self._make_controller_uri(aBrewPiController),
                                description="A BrewPi connected to a serial port, using the legacy protocol.",
                                connected=aBrewPiController.is_connected)

        self.controller = controller

        self.fire(ControllerConnected(controller))

        time.sleep(2)

        self.controller_state = self.controller_state_manager.get_for_controller(self.controller)

        # If we get a change from the service/user
        heater2pid = PID.query.filter(PID.profile==self.profile,
                                      PID.name=="heater2pid").one()

        heater2pid.kp = 20

        transaction = self.controller_state.begin_transaction()
        transaction.add(heater2pid)
        self.controller_state.commit(self.controller,
                                     transaction) # fire message

    def _on_controller_disconnected(self, aBrewPiController):
        self.fire(ControllerDisconncted(Controller(uri=self._make_controller_uri(aBrewPiController))))
