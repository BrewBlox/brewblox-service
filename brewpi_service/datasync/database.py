import logging

from ..database import db_session, get_or_create
from ..controller.models import Controller

from .abstract import AbstractSyncher

LOGGER = logging.getLogger(__name__)


class DatabaseSyncher(AbstractSyncher):
    """
    Synchronize controller states to a database
    """
    def on_controller_appeared(self, event):
        controller, created = get_or_create(db_session, Controller,
                                            create_method_kwargs={'name': 'Unnamed Controller',
                                                                  'description': 'Nice controller'},
                                            uri="http://xxxyyy",
                                            alive=True)

        LOGGER.debug("Controlled appeared: {0} -> new?{1}".format(controller, created))
        # import IPython; IPython.embed()
        # db_session.commit()

    def on_controller_disappeared(self, event):
        LOGGER.debug("Controlled disappeared: {0}", event.connector.conduit)
