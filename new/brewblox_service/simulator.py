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


def init_app(app: Type[web.Application]):
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


@routes.view('/config')
class ConfigView(web.View):
    """Allows getting and setting the simulator config."""

    async def get(self):
        sim = self.request.app['simulator']
        return web.json_response(sim.config)

    async def post(self):
        sim = self.request.app['simulator']
        sim.config = await self.request.json()
        return web.json_response(dict(success=True))


@routes.view('/values')
class ValuesView(web.View):
    """Allows getting randomized simulator state for all blocks."""

    def randomize(self, config: dict):
        for k, v in dpath.util.search(config, '**/state/*', yielded=True):
            new_val = 'value'
            if isinstance(v, bool):
                new_val = random.choice([True, False])
            elif isinstance(v, (int, float)):  # pragma: no cover (incorrectly flagged as not covered)
                new_val = random.random() / random.random()
            dpath.util.new(config, k, new_val)

    async def get(self):
        sim = self.request.app['simulator']
        self.randomize(sim.config)
        return web.json_response(sim.config)


@routes.view('/values/{id}')
class FilteredValuesView(ValuesView):
    """Allows getting randomized simulator state for a single block."""

    def filter(self, config: dict, id: str):
        for k, v in dpath.util.search(config, '**/identifier', yielded=True):
            if v == id:
                # return parent element of correct identifier
                return dpath.util.get(config, k.split('/')[:-1])
        # should not throw if identifier is absent
        return dict()

    async def get(self):
        id = self.request.match_info['id']
        sim = self.request.app['simulator']
        output = self.filter(sim.config, id)
        self.randomize(output)
        return web.json_response(output)
