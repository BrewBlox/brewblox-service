"""
Announces to ecosystem managers that plugin services are available.
"""

import logging
from typing import Type
from urllib.parse import urljoin

import requests
from flask import Flask
from requests.exceptions import ConnectionError

from brewblox_service import rest

LOGGER = logging.getLogger(__name__)
CREDENTIALS = {
    'username': 'admin',
    'password': 'admin'
}


def create_proxy_spec(app: Type[Flask]) -> dict:
    port = app.config['port']
    prefix = app.config['prefix']
    identifier = app.config['service_name']
    url = urljoin(f'http://localhost:{port}', prefix)

    spec = {
        'name': identifier,
        'active': True,
        'proxy': {
            # Strips 'listen_path'
            'strip_path': True,
            # Appends everything past 'listen_path'
            'append_path': True,
            # Alls calls that match this are forwarded
            'listen_path': f'/{identifier}/*',
            # HTTP methods of these types are forwarded
            'methods': rest.all_methods(),
            # Addresses to which requests are forwarded
            'upstreams': {
                'balancing': 'roundrobin',
                'targets': [{'target': url}]
            }
        },
        'health_check': {
            'url': url + '/_service/status'
        }
    }

    return spec


def auth_header(gateway: str) -> dict:
    res = requests.post(urljoin(gateway, 'login'), json=CREDENTIALS)
    headers = {'authorization': 'Bearer ' + res.json()['access_token']}
    return headers


def announce(app: Type[Flask]):
    gateway = app.config['gateway']
    service_name = app.config['service_name']

    try:
        url = urljoin(gateway, 'apis')
        spec = create_proxy_spec(app)
        headers = auth_header(gateway)

        LOGGER.debug(f'announcing spec: {spec}')

        # try to unregister previous instance of API
        delete_url = urljoin(gateway, f'apis/{service_name}')
        requests.delete(delete_url, headers=headers)

        # register service
        requests.post(url, headers=headers, json=spec)

    except ConnectionError as ex:
        LOGGER.warn(f'failed to announce to gateway: {str(ex)}')
