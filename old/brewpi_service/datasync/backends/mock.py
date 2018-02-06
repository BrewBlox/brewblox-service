import logging
from itertools import groupby
import time


from circuits import Component, handler

from brewpi_service.database import db_session
from brewpi_service.controller.models import Controller
from brewpi_service.controller.events import (
    ControllerConnected,
    ControllerBlockList
)

from brewpi_service.plugins_dir.temperature_sensor.models import TemperatureSensor, PID, SensorSetpointPair

from ..abstract import AbstractControllerSyncherBackend

from brewpi_service.controller.profile import ControllerProfileManager, NoResultFound
from brewpi_service.controller.state import ControllerStateManager

from brewpiv2.messages.temperature import TemperaturesMessage
from brewpiv2.messages.control import ControlSettingsMessage

from .brewpi_legacy import BrewPiLegacySyncherBackend

LOGGER = logging.getLogger(__name__)


class VirtualBrewPiSyncherBackend(Component, AbstractControllerSyncherBackend):
    """
    A virtual BrewPi Controller for testing purpose
    """
    def __init__(self, aControllerStateManager):
        super(VirtualBrewPiSyncherBackend, self).__init__()

        self.controller = None
        self.profile = None
        self.controller_state = None

        self._controller_state_manager = aControllerStateManager

        self.shutdown = False

    def make_profile(self, name="virtual_brewpi"):
        """
        Create the virtual profile
        """
        return BrewPiLegacySyncherBackend.make_profile(name)


    def started(self, *args):
        profile_name = "virtual_brewpi"
        try:
            self.profile = ControllerProfileManager.get(profile_name)
        except NoResultFound:
            self.profile = self.make_profile(name=profile_name)

        self.controller = Controller(name="Virtual BrewPi",
                                     uri="virtual://localhost",
                                     description="A virtual controller",
                                     profile=self.profile)

        self.controller_state = self._controller_state_manager.get_for_controller(self.controller)

        self.fire(ControllerConnected(self.controller))

        while not self.shutdown:
            # Send a list of available devices every second


            # If we get a message from the controller
            control_settings = ControlSettingsMessage(temp_format='C',
                                                      heater1_kp=0.8, heater1_ti=200, heater1_td=10,
                                                      heater1_infilter=12, heater1_dfilter=30, heater1_pwm_period=2,
                                                      heater2_kp=1.2, heater2_ti=100, heater2_td=3,
                                                      heater2_infilter=24, heater2_dfilter=10, heater2_pwm_period=1,
                                                      cooler_kp=2.0, cooler_ti=150, cooler_td=20,
                                                      cooler_infilter=10, cooler_dfilter=20, cooler_pwm_period=30,
                                                      min_cool_time=10, min_cool_idle_time=30,
                                                      beer2fridge_kp=0.1, beer2fridge_ti=2, beer2fridge_td=30,
                                                      beer2fridge_infilter=13, beer2fridge_dfilter=39, beer2fridge_pid_max=60,
                                                      deadtime=10)
            self.on_receive_control_settings(control_settings)


            # If we get a change from the service/user
            heater1pid = PID.query.filter(PID.name=="heater1pid").one()

            heater1pid.kp = 20

            transaction = self.controller_state.begin_transaction()
            transaction.add(heater1pid)
            self.controller_state.commit(self.controller,
                                         transaction) # fire message


            # Try to link a new sensor to heater2
            heater2pid = PID.query.filter(PID.name=="heater2pid").one()
            heater2pid.input = TemperatureSensor(object_id=99)

            transaction = self.controller_state.begin_transaction()
            transaction.add(heater2pid)
            self.controller_state.commit(self.controller,
                                         transaction) # fire message

            self.shutdown = True
            time.sleep(1)

    @handler("ControllerStateChangeRequest")
    def on_controller_state_change_request(self, event):
        for block in groupby(event.changes, key=lambda x: x[0]):

            control_changes = {}
            for change in block[1]:
                (block, fieldname, requested_value) = change
                if type(block) == PID:
                    ## SPECIFIC
                    if fieldname in ('input', ): # We have a link change
                        print("update link '{1}' on block {0} with object {2}".format(block, fieldname, requested_value))
                        if block.name in ('heater1pid', 'cooler1pid'):
                            InstallDeviceCommand(0, DeviceAssignation.CHAMBER, DeviceFunction.CHAMBER_TEMP, HardwareType.TEMP_SENSOR)
                        elif block.name == 'beer2fridgepid':
                            InstallDeviceCommand(0, DeviceAssignation.BEER, DeviceFunction.BEER_TEMP, HardwareType.TEMP_SENSOR)
                    elif fieldname in ('kp',):
                        print("collecting new data for {0} {1} {2}".format(block, fieldname, requested_value))
                        control_changes[fieldname] = requested_value
            if len(control_changes) > 0:
                print("sending control settings...")
                ControlSettingsCommand(heater1_kp=control_changes['kp'])

    def on_receive_control_settings(self, control_settings):
        """
        Feed the controller state system models from our backend values
        """
        try:
            heater1pid = self.profile.get_block_by_name('heater1pid')
        except NoResultFound:
            LOGGER.error("Profile mismatch on controller {0}".format(self.controller))

            return False

        self.controller_state.set(heater1pid, 'kp', control_settings.heater1_kp)

        return True

    # Event handlers
    @handler("ControllerRequestCurrentProfile")
    def on_request_current_profile(self):
        LOGGER.debug("Requesting current profile for controller {0}".format(self.controller))

        #self.fire(ControllerBlockList(self.controller,
        #                             [self.heater1_setpoint, self.temperature_sensor, self.heater1_pid]))
