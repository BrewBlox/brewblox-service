import logging
import platform
import time
from datetime import datetime, timedelta
from collections import OrderedDict

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
    ControllerBlockList,
    ControllerCleanStaleAvailableBlocks
)
from brewpi_service.controller.profile import (
    ControllerProfileManager,
    NoResultFound
)
from brewpi_service.controller.state import ControllerStateManager
from brewpi_service.controller.blocks.models import DigitalPin

from brewpi_service.plugins_dir.temperature_sensor.models import TemperatureSensor, PID, SensorSetpointPair, SetpointSimple


from ..abstract import AbstractControllerSyncherBackend

from .cache import available_blocks_cache


LOGGER = logging.getLogger(__name__)


class AvailableDevicePool:
    """
    Patch Object to assign an ID to available devices (which otherwise defaults
    to -1). The goal is to help trace them when updating.
    """
    def __init__(self):
        self._devices = {}

    def find_free_id(self):
        used_ids = self._devices.values()
        for i in range(10, 100):
            if -i not in used_ids:
                return -i

        raise Exception # FIXME

    def _hash_device(self, aDevice):
        return hash((aDevice.slot, aDevice.hardware_type, aDevice.pin, aDevice.address))

    def get_id_for(self, aDevice):
        id = None
        try:
            id = self._devices[self._hash_device(aDevice)]
        except KeyError:
            new_id = self.find_free_id()
            self._devices[self._hash_device(aDevice)] = new_id
            id = new_id

        return id


class BrewPiLegacySyncherBackend(Component, AbstractControllerSyncherBackend):
    """
    A loop that syncs a BrewPi Controller using the legacy firmware
    """
    def __init__(self, aControllerStateManager):
        super(BrewPiLegacySyncherBackend, self).__init__()

        self.manager = BrewPiControllerManager()
        self.msg_decoder = RawMessageDecoder()

        self._controller_state_manager = aControllerStateManager

        self.controller_observers = []

        self.shutdown = False

    @staticmethod
    def make_profile(name="brewpi_legacy"):
        """
        Create the brewpiv2 profile
        """
        LOGGER.info("Making BrewPi Legacy Profile into database under name '{0}'...".format(name))
        profile = ControllerProfileManager.create(name)

        beer1_setpoint = SetpointSimple(profile=profile,
                                        is_static=True,
                                        object_id=51,
                                        name="beer1set")
        db_session.add(beer1_setpoint)

        beer1_setpoint_pair = SensorSetpointPair(profile=profile,
                                                 name="heater1sensorsetpointpair",
                                                 setpoint=beer1_setpoint,
                                                 is_static=True,
                                                 # sensor=beer2_sensor,
                                                 object_id=61) # not required since static

        db_session.add(beer1_setpoint_pair)


        beer2_setpoint = SetpointSimple(profile=profile,
                                        is_static=True,
                                        object_id=52,
                                        name="beer2set")
        db_session.add(beer2_setpoint)

        beer2_setpoint_pair = SensorSetpointPair(profile=profile,
                                                 name="heater2sensorsetpointpair",
                                                 setpoint=beer2_setpoint,
                                                 is_static=True,
                                                 # sensor=beer2_sensor,
                                                 object_id=62) # not required since static

        db_session.add(beer2_setpoint_pair)

        # heater2_pwm = ActuatorPwm(profile=profile,
        #                           object_id=53,
        #                           period=4,
        #                           name="heater2pwm")

        # db_session.add(heater2_pwm)

        heater1_pid = PID(profile=profile,
                          name="heater1pid",
                          object_id=71,
                          is_static=True,
                          input=beer1_setpoint_pair)
                          # output=heater2_pwm)


        heater2_pid = PID(profile=profile,
                          name="heater2pid",
                          object_id=72,
                          is_static=True,
                          input=beer2_setpoint_pair)
                          # output=heater2_pwm)

        db_session.add(heater1_pid)
        db_session.add(heater2_pid)

        db_session.commit()

        return profile


    @handler("stopped")
    def stopped(self, *args):
        print("STOPPPEED")
        self.shutdown = True

    @handler("init")
    def init(self, *args):
        # Make sure we have our profile
        profile_name = "brewpi_legacy"
        try:
            self.profile = ControllerProfileManager.get(profile_name)
        except NoResultFound:
            self.profile = self.make_profile(name=profile_name)

        # wifi_ctrl = BrewPiController("socket://192.168.0.46:6666")
        # self.manager.controllers[wifi_ctrl.serial_port] = wifi_ctrl
        # controller_observer = BrewPiLegacyControllerObserver(wifi_ctrl,
        #                                                      self.profile,
        #                                                      self._controller_state_manager).register(self)
        # wifi_ctrl.subscribe(controller_observer)
        # wifi_ctrl.connect()

        # Remove all available devices

    @handler("started")
    def started(self, *args):
        last_update = datetime.utcnow()

        while not self.shutdown:
            if (datetime.utcnow() - last_update) > timedelta(seconds=5):
                LOGGER.debug("Requesting controller update from backend {0}".format(self))

                # Request list of available devices with values
                for port, controller in self.manager.controllers.items():
                    if controller.is_connected:
                        controller.send(ListAvailableDevicesCommand(with_values=True))
                        controller.send(ListInstalledDevicesCommand(with_values=True))

                # Clean up every cycle
                for observer in self.controller_observers:
                    observer.cleanup(last_update)

                last_update = datetime.utcnow()

            # Update manager
            for new_controller in self.manager.update():
                controller_observer = BrewPiLegacyControllerObserver(new_controller,
                                                                     self.profile,
                                                                     self._controller_state_manager).register(self)

                self.controller_observers.append(controller_observer)

                new_controller.subscribe(controller_observer)
                new_controller.connect()

            # Process messages from controllers
            for port, controller in self.manager.controllers.items():
                if controller.is_connected:
                    for raw_message in controller.process_messages():
                        for msg in self.msg_decoder.decode_controller_message(raw_message):
                            controller.notify(message_received, msg)

            # Dispatch updates to backstores
            for observer in self.controller_observers:
                observer.dispatch_and_clear_updates()

            yield

    def __str__(self):
        return "BrewPi Legacy Backend"


class SyncherMessageHandler(MessageHandler):
    """
    Take actions upon Controller Message reception
    """
    def __init__(self, aController, aControllerProfile):
        self.updated_blocks = []
        self.controller_profile = aControllerProfile
        self.controller = aController

        self.available_device_pool = AvailableDevicePool()

    def clear_updates(self):
        """
        Once updates have been treated, clear them for next update
        """
        self.updated_blocks = []

    def installed_device(self, aDevice):
        if aDevice.hardware_type == HardwareType.TEMP_SENSOR:
            self.updated_blocks.append(TemperatureSensor(object_id=aDevice.slot,
                                                         profile=self.controller_profile,
                                                         profile_id=self.controller_profile.id,
                                                         name="1-Wire Temperature Sensor@{0}".format(aDevice.address),
                                                         value=(aDevice.value, aDevice.value)))
        else:
            LOGGER.warn("Unknown installed device, ignoring.")

    def available_device(self, aDevice):
        if aDevice.hardware_type == HardwareType.DIGITAL_PIN:
            available_blocks_cache.add(self.controller,
                                       DigitalPin(object_id=self.available_device_pool.get_id_for(aDevice),
                                                  name="Digital Pin {0}".format(aDevice.pin),
                                                  pin_number=aDevice.pin,
                                                  is_inverted=aDevice.pin_inverted))

        elif aDevice.hardware_type == HardwareType.TEMP_SENSOR:
            available_blocks_cache.add(self.controller,
                                       TemperatureSensor(object_id=self.available_device_pool.get_id_for(aDevice),
                                                         value=(aDevice.value, aDevice.value), # Set actual value
                                                         name="1-Wire Temperature Sensor@{0}".format(aDevice.address)))
        else:
            LOGGER.debug("Unknown device to synch: {0}".format(aDevice))

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
        self.controller_state = None

        self.msg_handler = None

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

    def dispatch_and_clear_updates(self):
        if not self.msg_handler:
            return

        if len(self.msg_handler.updated_blocks) > 0:
            self.fire(ControllerBlockList(self.controller, self.msg_handler.updated_blocks))

        self.msg_handler.clear_updates()

    def _on_controller_connected(self, aBrewPiController):
        controller = Controller(name="BrewPi with legacy firmware on {0} at {1}".format(platform.node(),
                                                                                        aBrewPiController.serial_port),
                                profile_id=self.profile.id,
                                uri=self._make_controller_uri(aBrewPiController),
                                description="A BrewPi connected to a serial port, using the legacy protocol.",
                                connected=aBrewPiController.is_connected)

        self.controller = controller

        self.fire(ControllerConnected(controller))

        self.controller_state = self.controller_state_manager.get_for_controller(self.controller)

        # Create a message handler for this controller
        self.msg_handler = SyncherMessageHandler(self.controller, self.profile)

        # If we get a change from the service/user
        # heater2pid = PID.query.filter(PID.profile==self.profile,
        #                               PID.name=="heater2pid").one()

        # heater2pid.kp = 20

        # transaction = self.controller_state.begin_transaction()
        # transaction.add(heater2pid)
        # self.controller_state.commit(self.controller,
        #                              transaction) # fire message

    def _on_controller_disconnected(self, aBrewPiController):
        """
        Callback when a controller has been disconnected
        """
        self.fire(ControllerDisconnected(self.controller))

    def cleanup(self, limit_time):
        if self.controller:
            available_blocks_cache.cleanup_stale_blocks_for(self.controller)
            self.fire(ControllerCleanStaleAvailableBlocks(self.controller, limit_time))
