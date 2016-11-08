import logging
import coloredlogs

from flask_script import Manager

from brewpi_service import app
from brewpi_service.tasks import run_synchers

logger = logging.getLogger(__name__)
coloredlogs.install(level='DEBUG')

manager = Manager(app)

@manager.command
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
        print(line)


@manager.command
def run():
    # synchers_loop = run_synchers()
    app.run(debug=True)
    # synchers_loop.revoke(terminate=True)


if __name__ == "__main__":
    manager.run()
