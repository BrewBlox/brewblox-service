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


async def find_feature(app: Type[web.Application], feature: str, defaults: dict=DEFAULT_FEATURE_ADDR) -> dict:
    try:
        async with ClientSession() as session:
            res = await session.get(app['config']['consul'] + '/v1/catalog/service/' + feature)
            content = await res.json()

            LOGGER.debug(f'Feature discovery of [{feature}] yielded {content}')

            if not content:
                LOGGER.warn(f'Feature not found: [{feature}]')
                return defaults

            first = content[0]
            addr = dict(
                # We want Service if ServiceAddress is None or empty string
                host=first['ServiceAddress'] if first.get('ServiceAddress') else first['Address']
            )
            return addr

    except Exception as ex:
        LOGGER.warn(f'Feature discovery failed for [{feature}]: {str(ex)}')
        return defaults


@routes.get('/_debug/discover/{feature}')
async def request_feature(request: Type[web.Request]) -> Type[web.Response]:
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
