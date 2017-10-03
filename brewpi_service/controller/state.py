from collections import defaultdict

import logging

LOGGER = logging.getLogger(__name__)

class ControllerData(object):
    def __init__(self, *args, **kwargs):
        self._writable = False

        self._actual_value = None
        self._requested_value = None

        if 'writable' in kwargs:
            self._writable = True
            kwargs.pop('writable')

        self._args = args
        self._kwargs = kwargs


class VolatileStateMeta(type):
    def __new__(cls, classname, bases, dict_):
        cls.controller_data_fields = []

        for name, attribute in dict_.items():
            if type(attribute) is ControllerData:
                cls.controller_data_fields.append(name)

        return super().__new__(cls, classname, bases, dict_)



class BlockState(dict):
    pass

class ControllerState:
    def __init__(self):
        # {BLOCK_ID: {ATTR_NAME: (ACTUAL_VALUE, REQUESTED_VALUE)}}
        self.states = defaultdict(BlockState)

    def set(self, aBlock, attribute_name, value):
        self.states[aBlock.object_id][attribute_name] = (value, None)

    def request(self, aBlock, attribute_name, value):
        if self.states[aBlock.object_id].has_key(attribute_name):
            self.states[aBlock.object_id][attribute_name][1] = value
        else:
            self.states[aBlock.object_id][attribute_name] = (None, value)

class ControllerStateManager:
    def __init__(self):
        self.states = defaultdict(ControllerState)

    def get_for_controller(self, aController):
        return self.states[aController]

ControllerStateManager = ControllerStateManager()
