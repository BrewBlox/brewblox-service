"""
Tests brewblox_service.announcer.py
"""

from brewblox_service import announcer, rest

TESTED = 'brewblox_service.announcer'


def test_create_proxy_spec(app):
    spec = announcer.create_proxy_spec(app)

    assert spec == {
        'name': 'test_name',
        'active': True,
        'proxy': {
            'strip_path': True,
            'append_path': True,
            'listen_path': '/test_name/*',
            'methods': rest.all_methods(),
            'upstreams': {
                'balancing': 'roundrobin',
                'targets': [{'target': 'http://localhost:1234'}]
            }
        },
        'health_check': {
            'url': 'http://localhost:1234/_service/status'
        }
    }


def test_auth_header(mocker):
    req_mock = mocker.patch(TESTED + '.requests')
    req_mock.post.return_value.json.return_value = {
        'access_token': 'tokkie'
    }

    res = announcer.auth_header('http://gateway')

    assert res == {'authorization': 'Bearer tokkie'}
    req_mock.post.assert_called_once_with(
        'http://gateway/login',
        json={
            'username': 'admin',
            'password': 'admin'
        })


def test_announce_err(mocker, app):
    log_mock = mocker.patch(TESTED + '.LOGGER')
    announcer.announce(app)
    assert log_mock.warn.call_count == 1


def test_announce(mocker, app):
    headers = {'auth': 'val'}
    spec = announcer.create_proxy_spec(app)

    req_mock = mocker.patch(TESTED + '.requests')
    mocker.patch(TESTED + '.auth_header').return_value = headers

    announcer.announce(app)

    req_mock.delete.assert_called_once_with(
        'http://gatewayaddr:1234/apis/test_name', headers=headers)
    req_mock.post.assert_called_once_with(
        'http://gatewayaddr:1234/apis', headers=headers, json=spec)
