from collections import defaultdict, UserList

from circuits import Component

from .events import ControllerStateChangeRequest

import logging

LOGGER = logging.getLogger(__name__)


class ControllerDataField(UserList):
    (ACTUAL, REQUESTED, DIRTY) = range(3)

    def __init__(self, *args, **kwargs):
        self._writable = False

        if 'writable' in kwargs:
            self._writable = True
            kwargs.pop('writable')

        self._args = args
        self._kwargs = kwargs

        super(ControllerDataField, self).__init__([None, None, False])

    def set_actual_value(self, value):
        self.data[ControllerDataField.ACTUAL] = value

    def request_value(self, value):
        if value != self.get_actual_value():
            self.data[ControllerDataField.REQUESTED] = value
            self.data[ControllerDataField.DIRTY] = True

    def get_requested_value(self):
        return self.data[ControllerDataField.REQUESTED]

    def get_actual_value(self):
        return self.data[ControllerDataField.ACTUAL]


class BlockState(defaultdict):
    def __init__(self):
        super(BlockState, self).__init__(lambda: [None, None])


class ControllerState(Component):
    """
    The simplest, most universal way of representing a controller state: a
    dictionary of block IDs themselfves composed of dictionaries of attributes.
    Example:
      - {BLOCK_ID: {ATTR_NAME: (CURRENT_VALUE, REQUESTED_VALUE)}}
    """
    def __init__(self, aControllerStateManager):
        self.states = defaultdict(BlockState)

        self._controller_state_manager = aControllerStateManager

    def set(self, aBlock, attribute_name, value):
        self.states[aBlock.object_id][attribute_name] = [value, None]

    def set_requested(self, aBlock, attribute_name, value):
        attr_data = self.get(aBlock, attribute_name)
        attr_data[1] = value

    def get(self, aBlock, attribute_name):
        return self.states[aBlock.object_id][attribute_name]

    def get_requested(self, aBlock, attribute_name):
        return self.get(aBlock, attribute_name)[1]

    def get_actual(self, aBlock, attribute_name):
        return self.get(aBlock, attribute_name)[0]

    def begin_transaction(self):
        return ControllerStateTransaction()

    def commit(self, aController, aControllerStateTransaction):
        changes = aControllerStateTransaction.get_compiled_changes()

        self._controller_state_manager.commit_state(aController, changes)

        # Empty transaction
        aControllerStateTransaction.clear() # as callback?


class ControllerStateTransaction:
    def __init__(self):
        self.dirty_blocks = []

    def add(self, aBlock):
        self.dirty_blocks.append(aBlock)

    def clear(self):
        """
        Clear transaction
        """
        self.dirty_blocks = []

    def get_compiled_changes(self):
        # Collect changed fields
        changes = []

        for block in self.dirty_blocks:
            for fieldname in block.get_dirty_fields():
                field = getattr(block, fieldname)
                changes.append((block, fieldname, field.get_requested_value()))

        return changes

class ControllerStateManager(Component):
    """
    The manager holding states for every Controller registered
    Shoud be seen as a Singleton
    """
    def __init__(self):
        self.states = defaultdict(lambda: ControllerState(self))
        super(ControllerStateManager, self).__init__()

    def get_for_controller(self, aController):
        return self.states[aController]

    def commit_state(self, aController, changes):
        state = self.get_for_controller(aController)
        for change in changes:
            state.set_requested(change[0], change[1], change[2])

        LOGGER.debug("Commiting changes for controller {0}".format(aController))
        self.fire(ControllerStateChangeRequest(aController, changes))
