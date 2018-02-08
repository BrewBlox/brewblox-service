import logging
from typing import Type

from flask import Flask, jsonify
from flask.views import MethodView
from flask_plugins import PluginManager, get_enabled_plugins, get_plugin

from brewblox_service import rest

LOGGER = logging.getLogger(__name__)


class PluginsView(MethodView):
    def get(self):
        return jsonify([p for p in get_enabled_plugins()])


class PluginDetailsView(MethodView):
    def get(self, id: str):
        return jsonify(get_plugin(id))


def init_app(app: Type[Flask]):
    rest.register(app, '/system/plugins', PluginsView)
    rest.register(app, '/system/plugins/<id>', PluginDetailsView)

    plugin_dir = app.config['plugin_dir']
    logging.info('Looking for plugins in "{}"'.format(plugin_dir))

    try:
        mgr = PluginManager(app, plugin_folder=plugin_dir)
        LOGGER.info('Found plugins: {}'.format(mgr.plugins))
    except FileNotFoundError as ex:
        LOGGER.exception(ex)
        LOGGER.warn('Plugin directory "{}" not found'.format(plugin_dir))
