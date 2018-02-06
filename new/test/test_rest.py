"""
Test functions for brewblox_service.rest
"""

from brewblox_service import rest
from unittest.mock import Mock


def test_api(mocker):
    specs_mock = mocker.patch('brewblox_service.rest.FlaskApiSpec').return_value
    view_mock = Mock()
    view_mock.__name__ = 'mock_name'
    endpoint_mock = view_mock.as_view.return_value
    app_mock = Mock()

    api = rest.Api('prefix/')
    api.register('/end/point', view_mock)
    api.init_app(app_mock)

    specs_mock.register.assert_called_once_with(endpoint_mock)
    specs_mock.init_app.assert_called_once_with(app_mock)
    app_mock.add_url_rule.assert_called_once_with('/prefix/end/point', view_func=endpoint_mock)
