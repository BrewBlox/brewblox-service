"""
Announces to ecosystem managers that plugin services are available.
"""

import logging
from typing import Type
from urllib.parse import urljoin

from aiohttp import ClientSession, hdrs, web

LOGGER = logging.getLogger(__name__)
CREDENTIALS = {
    'username': 'admin',
    'password': 'admin'
}


async def create_proxy_spec(name: str, host: str, port: int) -> dict:
    """Defines behavior for how the gateway should reverse proxy REST calls.

    Example:
        gateway url = http://gateway:1234
        controller url = http://controlhost:5678
        controller name = my_controller

        The gateway forwards all paths starting with 'my_controller'.

        Example call:
        to gateway: http://gateway:1234/my_controller/api/doc
        proxied to: http://controlhost:5678/my_controller/api/doc

    """
    url = f'http://{host}:{port}'

    spec = {
        'name': name,
        'active': True,
        'proxy': {
            # listen path is part of actual endpoint
            'strip_path': False,
            # Appends everything past 'listen_path'
            'append_path': True,
            # Alls calls that match this are forwarded
            'listen_path': f'/{name}/*',
            # HTTP methods of these types are forwarded
            'methods': list(hdrs.METH_ALL),
            # Addresses to which requests are forwarded
            'upstreams': {
                'balancing': 'roundrobin',
                'targets': [{'target': url}]
            }
        },
        'health_check': {
            'url': f'{url}/{name}/_service/status'
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

            LOGGER.debug(f'Announcing spec: {spec}')

            # try to unregister previous instance of API
            delete_url = urljoin(gateway, f'apis/{name}')
            await session.delete(delete_url, headers=headers)

            # register service
            await session.post(url, headers=headers, json=spec)

            LOGGER.info(f'Announced to {url} as [{name}]')

        except Exception as ex:
            LOGGER.warn(f'Failed gateway announce: {str(ex)}')
