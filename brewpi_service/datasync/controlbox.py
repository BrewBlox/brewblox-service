import logging
import time

# from brewpi.controlbox.codecs.time import (
#    BrewpiStateCodec, BrewpiConstructorCodec
#)
# from brewpi.protocol.factory import all_sniffers
# from controlbox.connector_facade import ControllerDiscoveryFacade
from controlbox.protocol.io import determine_line_protocol
from controlbox.controller import Controlbox
# from brewpi.connector.controlbox.objects import BrewpiController, BuiltInObjectTypes
# from controlbox.events import (
#    ControlboxEvents, ConnectorCodec, ConnectorEventVisitor
# )

# from controlbox.connector.base import (
#    ConnectorConnectedEvent, ConnectorDisconnectedEvent
# )
# from controlbox.protocol.controlbox import ControlboxProtocolV1
# from controlbox.connector.socketconn import TCPServerEndpoint

from .database import DatabaseControllerSyncher

LOGGER = logging.getLogger(__name__)

ConnectorEventVisitor = object # FIXME

class BrewpiEvents(ConnectorEventVisitor):
    """
    Handle events for one controller
    """
    handlers = {}

    def __init__(self, aController):
        self._controller = aController

    def __call__(self, event):
        LOGGER.debug(event)
        if event.type == 1:  # XXX Should be a constant here, not int
            state_type = type(event.state)
            if state_type in self.handlers:
                self.handlers[state_type].update(self._controller,
                                                 event.state,
                                                 event)


def sniffer(conduit):
    return determine_line_protocol(conduit, all_sniffers)


class ControlboxSyncher(DatabaseControllerSyncher):
    """
    A loop that syncs to the controller using Controlbox/Connector
    """
    # discoveries = [
    #    ControllerDiscoveryFacade.build_serial_discovery(sniffer),
    #    ControllerDiscoveryFacade.build_tcp_server_discovery(sniffer, "brewpi",
    #                                                         known_addresses=()),
    # ]

    def __init__(self):
        self.facade = ControllerDiscoveryFacade(self.discoveries)

        self.facade.manager.events.add(self._handle_connection_event)  # connected?

    def _dump_device_info_events(self, connector, protocol):
        """
        XXX Document that
        """
        if not hasattr(protocol, 'controller'):
            protocol.controller = Controlbox(connector)
            events = protocol.controller.events = ControlboxEvents(protocol.controller, BrewpiConstructorCodec(), BrewpiStateCodec())
            controller = BrewpiController(connector, BuiltInObjectTypes())
            controller.initialize(True)
            events.listeners.add(BrewpiEvents(controller))
        else:
            events = protocol.controller.events

        # todo - would be good if the system itself described the type as part of the read response
        # this makes the system more self-describing
        events.read_system([0], 0)
        events.read_system([1], 1)

    def _handle_connection(self, connection):
        """
        XXX Doc
        """
        connector = connection.connector
        if connector.connected:
            self._dump_device_info_events(connector, connector.protocol)

    def _handle_connection_event(self, event):
        """
        Callback when a controller (dis)appears
        """
        if type(event) == ConnectorConnectedEvent:
            self.on_controller_appeared(event)
        elif type(event) == ConnectorDisconnectedEvent:
            self.on_controller_disappeared(event)

    def run(self):
        while True:
            self.facade.update()

            for connection in self.facade.manager.connections.values():
                self._handle_connection(connection)

            time.sleep(1)
