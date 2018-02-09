import logging
from typing import Type

from flask import Flask, jsonify, abort
from flask.views import MethodView
from flask_plugins import PluginManager, get_enabled_plugins, get_plugin

from brewblox_service import rest

LOGGER = logging.getLogger(__name__)


class PluginsView(MethodView):
    def get(self):
        return jsonify([p.identifier for p in get_enabled_plugins()])


class PluginDetailsView(MethodView):
    def get(self, id: str):
        try:
            return jsonify(get_plugin(id).info)
        except KeyError:
            LOGGER.warn('Plugin "{}" not found'.format(id))
            abort(400)


def init_app(app: Type[Flask]):
    rest.register(app, '/system/plugins', PluginsView)
    rest.register(app, '/system/plugins/<id>', PluginDetailsView)

    plugin_dir = app.config['plugin_dir']
    LOGGER.info('Looking for plugins in "{}"'.format(plugin_dir))

    try:
        mgr = PluginManager(app, plugin_folder=plugin_dir)
        LOGGER.info('Found plugins: {}'.format(mgr.plugins))
        for m in mgr.plugins.values():
            getattr(m, 'init_app') and m.init_app(app)
    except FileNotFoundError as ex:
        LOGGER.warn('Plugin directory "{}" not found'.format(plugin_dir))
