from brewpi_service import app
from brewpi_service.tasks import run_synchers

import logging
import coloredlogs

logger = logging.getLogger('service')
coloredlogs.install(level='DEBUG')

synchers_loop = run_synchers()
app.run(debug=True)
synchers_loop.revoke(terminate=True)
