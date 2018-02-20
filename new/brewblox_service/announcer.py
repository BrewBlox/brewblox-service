"""
Announces to ecosystem managers that plugin services are available.
"""

import logging
from typing import Type
from urllib.parse import urljoin

from aiohttp.client_exceptions import ClientConnectorError
from aiohttp import web, ClientSession

LOGGER = logging.getLogger(__name__)
CREDENTIALS = {
    'username': 'admin',
    'password': 'admin'
}
ALL_METHODS = [
    'GET',
    'HEAD',
    'POST',
    'PUT',
    'DELETE',
    'CONNECT',
    'OPTIONS',
    'TRACE',
    'PATCH'
]


async def create_proxy_spec(name: str, host: str, port: int) -> dict:
    url = f'http://{host}:{port}'

    spec = {
        'name': name,
        'active': True,
        'proxy': {
            # Strips 'listen_path'
            'strip_path': True,
            # Appends everything past 'listen_path'
            'append_path': True,
            # Alls calls that match this are forwarded
            'listen_path': f'/{name}/*',
            # HTTP methods of these types are forwarded
            'methods': ALL_METHODS,
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


async def auth_header(session: Type[ClientSession], gateway: str) -> dict:
    async with session.post(urljoin(gateway, 'login'), json=CREDENTIALS) as res:
        content = await res.json()
        headers = {'authorization': 'Bearer ' + content['access_token']}
        return headers


async def announce(app: Type[web.Application]):
    config = app['config']
    gateway = config['gateway']
    name = config['name']
    host = config['host']
    port = config['port']

    async with ClientSession() as session:
        try:
            url = urljoin(gateway, 'apis')
            spec = await create_proxy_spec(name, host, port)
            headers = await auth_header(session, gateway)

            LOGGER.debug(f'announcing spec: {spec}')

            # try to unregister previous instance of API
            delete_url = urljoin(gateway, f'apis/{name}')
            await session.delete(delete_url, headers=headers)

            # register service
            await session.post(url, headers=headers, json=spec)

        except ClientConnectorError as ex:
            LOGGER.warn(f'failed to announce to gateway: {str(ex)}')
