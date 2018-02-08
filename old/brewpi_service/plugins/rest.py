from flask import jsonify

from brewpi_service import app

from .core import plugin_manager, get_plugin
from .schemas import plugin_schema, plugins_schema


@app.route('/system/plugins/')
def plugins():
    """
    List Plugins
    """
    all_plugins = []
    for name, plugin in plugin_manager.all_plugins.items():
        all_plugins.append(plugin)

    result = plugins_schema.dump(all_plugins)
    return jsonify(result.data)


@app.route('/system/plugins/<id>')
def plugin_detail(id):
    """
    Detail a given Plugin
    """
    plugin = get_plugin(id)
    return plugin_schema.jsonify(plugin)
