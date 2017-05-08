#!/usr/bin/env python
import logging

import click

from brewpi_service import app
from brewpi_service.plugins.core import plugin_manager

LOGGER = logging.getLogger(__name__)

@app.cli.command()
def list_routes():
    from urllib.parse import unquote
    from flask import url_for
    output = []
    for rule in app.url_map.iter_rules():

        options = {}
        for arg in rule.arguments:
            options[arg] = "[{0}]".format(arg)

        methods = ','.join(rule.methods)
        url = url_for(rule.endpoint, **options)
        line = unquote("{:50s} {:20s} {}".format(rule.endpoint, methods, url))
        output.append(line)

    for line in sorted(output):
        click.echo(line)


@app.cli.command()
def list_plugins():
    for name, plugin in plugin_manager.all_plugins.items():
        print("{0} [{1}] - {2} (from: {3})".format(name,
                                             '✓' if plugin.enabled else '✗',
                                             plugin.description,
                                             plugin.path))

@app.cli.command()
def initdb():
    from brewpi_service.database import init_db
    click.echo("Initializing db...")
    init_db()


@app.cli.command()
def workers():
    from brewpi_service import app, create_worker_app
    create_worker_app(app)
