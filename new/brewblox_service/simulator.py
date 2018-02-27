"""
Default service implementation: a simulator
"""

import logging
import random
from pprint import pformat
from typing import Type

import dpath
from aiohttp import web

LOGGER = logging.getLogger(__name__)
routes = web.RouteTableDef()


def setup(app: Type[web.Application]):
    app.router.add_routes(routes)
    app['simulator'] = SimulatorService()


class SimulatorService():
    """Responsible for making functionality available to the app.

    Keeps an internal 'config' object to mimic block configuration.
    The config makes some assumptions:
    * There are unique 'identifier' keys.
    * Volatile state objects are contained in a 'state' dict

    Example config:
    [
        {
            'identifier': 'unique_name',
            'state': {
                'value1': 1.2,
                'value2': True,
                'value3', 'stuff
            }
        }
    ]
    """

    def __init__(self):
        self._config = {}

    @property
    def config(self):
        return self._config

    @config.setter
    def config(self, val: dict):
        assert val
        LOGGER.info(f'updating simulator config to \n{pformat(val)}')
        self._config = val

    def randomize(self, config: dict):
        for k, v in dpath.util.search(config, '**/state/*', yielded=True):
            new_val = 'value'
            if isinstance(v, bool):
                new_val = random.choice([True, False])
            elif isinstance(v, (int, float)):  # pragma: no cover (incorrectly flagged as not covered)
                new_val = random.random() / random.random()
            dpath.util.new(config, k, new_val)

    def filter(self, config: dict, id: str):
        for k, v in dpath.util.search(config, '**/identifier', yielded=True):
            if v == id:
                # return parent element of correct identifier
                return dpath.util.get(config, k.split('/')[:-1])
        # should not throw if identifier is absent
        return dict()


@routes.get('/config')
async def get_config(request):
    """
    ---
    tags:
    - Simulator
    summary: Get current config.
    description: Get config currently used by simulator.
    operationId: simulator.config
    produces:
    - application/json
    """
    sim = request.app['simulator']
    return web.json_response(sim.config)


@routes.post('/config')
async def post_config(request):
    """
    ---
    tags:
    - Simulator
    summary: Update config.
    description: Set new configuration to be returned by simulator.
    operationId: simulator.config
    produces:
    - application/json
    parameters:
    -
        in: body
        name: body
        description: New configuration
        required: true
        schema:
            type: array
            items:
                properties:
                    identifier:
                        type: string
                    name:
                        type: string
                    type_id:
                        type: integer
                        format: int64
                    state:
                        type: object
                    settings:
                        type: object
    """
    sim = request.app['simulator']
    sim.config = await request.json()
    return web.json_response(dict(success=True))


@routes.get('/values')
async def get_values(request):
    """
    ---
    tags:
    - Simulator
    summary: Get all config values.
    description: Get randomized state for all values currently in config.
    operationId: simulator.values
    produces:
    - application/json
    """
    sim = request.app['simulator']
    sim.randomize(sim.config)
    return web.json_response(sim.config)


@routes.get('/values/{id}')
async def get_specific_value(request):
    """
    ---
    tags:
    - Simulator
    summary: Get all config values.
    description: Get randomized state for all values matching a specific identifier.
    operationId: simulator.values.id
    produces:
    - application/json
    parameters:
    -
        name: id
        in: path
        required: true
        description: the unique identifier of the desired value
        schema:
            type: string
    """
    id = request.match_info['id']
    sim = request.app['simulator']
    output = sim.filter(sim.config, id)
    sim.randomize(output)
    return web.json_response(output)
