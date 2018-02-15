import logging
from typing import Type
import importlib

from flask import Flask, jsonify, abort
from flask.views import MethodView
from flask_plugins import PluginManager, get_enabled_plugins, get_plugin

from brewblox_service import rest

LOGGER = logging.getLogger(__name__)


class PluginsView(MethodView):
    def get(self):
        plugins = []
        try:
            plugins = [p.identifier for p in get_enabled_plugins()]
        except AttributeError as ex:
            # get_enabled_plugins() throws if no plugins were found.
            # we can ignore this.
            pass
        return jsonify(plugins)


class PluginDetailsView(MethodView):
    def get(self, id: str):
        try:
            return jsonify(get_plugin(id).info)
        except KeyError:
            LOGGER.warn('Plugin "{}" not found'.format(id))
            abort(400)


def init_app(app: Type[Flask]):
    rest.register(app, '/_service/plugins', PluginsView)
    rest.register(app, '/_service/plugins/<id>', PluginDetailsView)

    plugin_dir = app.config['plugin_dir']

    if not importlib.util.find_spec(app.name):
        LOGGER.warn('No module named "{}" - unable to load plugins.'.format(app.name))
        return

    try:
        mgr = PluginManager(app, plugin_folder=plugin_dir)
        LOGGER.info('Plugin directory: "{}"'.format(mgr.plugin_folder))
        LOGGER.info('Available plugins: {}'.format([*mgr.plugins.keys()]))
    except FileNotFoundError as ex:
        LOGGER.warn('Failed to load plugins: {}'.format(ex))
