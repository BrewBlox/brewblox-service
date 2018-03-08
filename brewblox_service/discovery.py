"""
Matches a service name to an accessible URL
"""

import logging
from aiohttp import ClientSession, web
from typing import Type

LOGGER = logging.getLogger(__name__)
routes = web.RouteTableDef()

DEFAULT_FEATURE_ADDR = {
    'host': 'localhost',
}


def setup(app: Type[web.Application]):
    app.router.add_routes(routes)


async def find_feature(app: Type[web.Application], feature: str, defaults: dict=DEFAULT_FEATURE_ADDR):
    try:
        async with ClientSession() as session:
            res = await session.get('http://consul:8500/v1/catalog/service/' + feature)
            content = await res.json()

            LOGGER.debug(f'Discovery of [{feature}] yielded {content}')

            if not content:
                return defaults

            first = content[0]
            addr = dict(
                # We want Service if ServiceAddress is None or empty string
                host=first['ServiceAddress'] if first.get('ServiceAddress') else first['Address']
            )
            return addr

    except Exception as ex:
        LOGGER.warn(f'Failed service discovery for [{feature}]: {str(ex)}')
        return defaults


@routes.get('/_debug/discover/{feature}')
async def request_feature(request: Type[web.Request]):
    """
    ---
    tags:
    - Discovery
    - Debug
    summary: discover feature.
    description: let this service query where it can reach a feature.
    operationId: discovery.discover
    produces:
    - application/json
    parameters:
    -
        name: feature
        in: path
        required: true
        description: feature service name
        schema:
            type: string
    """
    feature = request.match_info['feature']
    return web.json_response(await find_feature(request.app, feature))


@routes.post('/_debug/sendto/{feature}')
async def sendto_feature(request: Type[web.Request]):
    """
    ---
    tags:
    - Discovery
    - Debug
    summary: send request to feature service.
    description: discover a feature, and then send a request to it from this service.
    operationId: discovery.sendto
    produces:
    - application/json
    parameters:
    -
        name: feature
        in: path
        required: true
        description: feature service name
        schema:
            type: string
    -
        in: body
        name: body
        description: Request data
        schema:
            type: object
            properties:
                endpoint:
                    type: string
                data:
                    type: object
    """
    feature = request.match_info['feature']
    feature_addr = await find_feature(request.app, feature)
    content = await request.json()
    async with ClientSession() as session:
        addr = 'http://' + feature_addr['host'] + ':5000'
        addr += content['endpoint']
        LOGGER.info(f'Sending to {addr}')
        res = await session.post(addr, json=content['data'])
        return web.json_response(await res.text())
