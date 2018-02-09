"""
Defines the name of the Plugin class offered by this plugin
"""
from flask_plugins import Plugin
# from brewblox_service import rest

__plugin__ = 'SimulatorPlugin'


class SimulatorPlugin(Plugin):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.config = {}

    def init_app(self, app):
        pass
