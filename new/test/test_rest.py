"""
Test functions for brewblox_service.rest
"""

from brewblox_service import rest
from unittest.mock import Mock, call


def test_register():
    view_mock = Mock()
    view_mock.__name__ = 'mock_name'
    endpoint_mock = view_mock.as_view.return_value

    app_mock = Mock()
    app_mock.config = {'prefix': '/prefix'}

    rest.register(app_mock, '/end/point', view_mock)
    rest.register(app_mock, '///nested/end/point//', view_mock)
    rest.register(app_mock, 'param/view', view_mock, param1='stuff', param2='val')

    app_mock.add_url_rule.assert_has_calls([
        call('/prefix/end/point', view_func=endpoint_mock),
        call('/prefix/nested/end/point', view_func=endpoint_mock),
        call('/prefix/param/view', view_func=endpoint_mock)
    ])

    view_mock.as_view.assert_has_calls([
        call(name='mock_name'),
        call(name='mock_name'),
        call(name='mock_name', param1='stuff', param2='val'),
    ])


def test_shutdown(mocker, app, client):
    endpoint = '/_service/shutdown'
    assert client.post(endpoint).status_code == 500

    shutdown_mock = Mock()
    request_mock = mocker.patch('brewblox_service.rest.request')
    request_mock.environ.get.return_value = shutdown_mock

    assert client.post(endpoint).status_code == 200
    assert shutdown_mock.call_count == 1


def test_healthcheck(app, client):
    endpoint = '/_service/status'

    res = client.get(endpoint)
    assert res.status_code == 200
    assert res.json == {'status': 'ok'}


def test_all_methods():
    assert 'GET' in rest.all_methods()
