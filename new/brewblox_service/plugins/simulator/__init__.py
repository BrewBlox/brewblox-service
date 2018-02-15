"""
Flask plugin implementation of a generic simulator for brewblox_service
"""
import logging
import random
from pprint import pformat
from typing import Type

import dpath
from flask import jsonify, request, current_app
from flask.views import MethodView
from flask_plugins import Plugin

from brewblox_service import rest

__plugin__ = 'SimulatorPlugin'


LOGGER = logging.getLogger(__plugin__)


class SimulatorPlugin(Plugin):
    """Responsible for making functionality available to the Flask app.

    Keeps an internal 'config' object to mimic block configuration.
    The config makes some assumptions:
    * There are unique 'identifier' keys.
    * Volatile state objects are contained in a 'state' dict

    Example config:
    [
        {
            'identifier': 'unique_name',
            'state': {
                'value1': 1.2,
                'value2': True,
                'value3', 'stuff
            }
        }
    ]
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._config = {}

    def setup(self):
        """Performs setup steps - this is done inside the app context"""
        rest.register(current_app, '/config', ConfigView, plugin=self)
        rest.register(current_app, '/values/<string:id>',
                      FilteredValuesView, plugin=self)
        rest.register(current_app, '/values/', ValuesView, plugin=self)

    @property
    def config(self):
        return self._config

    @config.setter
    def config(self, val: dict):
        assert val
        LOGGER.info('updating [{}] config to \n{}'
                    .format(__plugin__, pformat(val)))
        self._config = val


class ConfigView(MethodView):
    """Allows getting and setting the simulator config."""

    def __init__(self, plugin: Type[SimulatorPlugin]=None):
        self.plugin = plugin

    def get(self):
        return jsonify(self.plugin.config)

    def post(self):
        assert request.json
        self.plugin.config = request.json
        return jsonify(dict(success=True))


class ValuesView(MethodView):
    """Allows getting randomized simulator state for all blocks."""

    def __init__(self, plugin: Type[SimulatorPlugin]=None):
        self.plugin = plugin

    def randomize(self, config: dict):
        for k, v in dpath.util.search(config, '**/state/*', yielded=True):
            new_val = 'value'
            if isinstance(v, bool):
                new_val = random.choice([True, False])
            elif isinstance(v, (int, float)):  # pragma: no cover (incorrectly flagged as not covered)
                new_val = random.random() / random.random()
            dpath.util.new(config, k, new_val)

    def get(self):
        self.randomize(self.plugin.config)
        return jsonify(self.plugin.config)


class FilteredValuesView(ValuesView):
    """Allows getting randomized simulator state for a single block."""

    def filter(self, config: dict, id: str):
        for k, v in dpath.util.search(config, '**/identifier', yielded=True):
            if v == id:
                # return parent element of correct identifier
                return dpath.util.get(config, k.split('/')[:-1])
        # should not throw if identifier is absent
        return dict()

    def get(self, id: str):
        output = self.filter(self.plugin.config, id)
        self.randomize(output)
        return jsonify(output)
