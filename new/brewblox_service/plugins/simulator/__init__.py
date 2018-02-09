"""
Defines the name of the Plugin class offered by this plugin
"""
import logging
from pprint import pprint
from typing import Type

from flask import request, jsonify
from flask.views import MethodView
from flask_plugins import Plugin

from brewblox_service import rest

__plugin__ = 'SimulatorPlugin'


LOGGER = logging.getLogger(__plugin__)


class SimulatorPlugin(Plugin):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._config = {}

    def init_app(self, app):
        rest.register(app, '/simulator/config', ConfigView, plugin=self)

    @property
    def config(self):
        return self._config

    @config.setter
    def config(self, val: dict):
        assert val
        LOGGER.info('updating [{}] config to \n{}'
                    .format(__plugin__, pprint(val)))
        self._config = val


class ConfigView(MethodView):
    def __init__(self, plugin: Type[SimulatorPlugin]=None):
        self.plugin = plugin

    def get(self):
        return jsonify(self.plugin.config)

    def post(self):
        assert request.json
        self.plugin.config = request.json
        return jsonify(dict(success=True))
