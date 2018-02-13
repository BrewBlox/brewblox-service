"""
Tests brewblox_service.plugger.py
"""

from brewblox_service import plugger
from unittest.mock import call


def test_init(mocker, app):
    rest_mock = mocker.patch('brewblox_service.plugger.rest')

    plugger.init_app(app)

    rest_mock.register.assert_has_calls([
        call(app, '/system/plugins', plugger.PluginsView),
        call(app, '/system/plugins/<id>', plugger.PluginDetailsView)
    ])


def test_endpoints(app, client):
    plugger.init_app(app)

    # enumerate all plugins
    res = client.get('/system/plugins')
    assert res.status_code == 200
    assert res.json == ['simulator']

    # no plugin found with ID '1'
    assert client.get('/system/plugins/1').status_code == 400

    # simulator can be found
    res = client.get('/system/plugins/simulator')
    assert res.status_code == 200
    assert res.json
    assert res.json['identifier'] == 'simulator'
    assert res.json['name'] == 'BrewBlox Block Simulator'


def test_no_plugin_dir(mocker, app):
    log_mock = mocker.patch('brewblox_service.plugger.LOGGER')
    app.config['plugin_dir'] = 'narnia'
    plugger.init_app(app)
    assert log_mock.warn.call_count > 0


def test_invalid_app(mocker, app):
    mgr_mock = mocker.patch('brewblox_service.plugger.PluginManager')
    app.name = 'absolute nonsense'
    plugger.init_app(app)
    assert mgr_mock.call_count == 0
