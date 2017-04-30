import logging

from basicevents import subscribe

from brewpi_service.database import db_session, get_or_create
from brewpi_service.controller.models import Controller

from ..abstract import AbstractBackstoreSyncher


LOGGER = logging.getLogger(__name__)


class DatabaseSyncher(AbstractBackstoreSyncher):
    """
    Synchronize backend events to a Database using SQLAlchemy
    """
    @staticmethod
    @subscribe("controller.connected")
    def on_controller_appeared(aController):
        controller, created = get_or_create(db_session, Controller,
                                            create_method_kwargs={'name': aController.name,
                                                                  'description': aController.description,
                                                                  'connected': aController.connected},
                                            uri=aController.uri)

        if created is False:
            controller.connected = True
            LOGGER.debug("Controller has reconnected: {0}".format(controller))
        else:
            LOGGER.debug("New Controller connected: {0}".format(controller))

        db_session.commit()

    @staticmethod
    @subscribe("controller.disconnected")
    def on_controller_disappeared(aController):
        LOGGER.debug("Controller disconnected: {0}".format(aController.uri))
        controller = db_session.query(Controller).filter(Controller.uri == aController.uri).first()
        controller.connected = False

        db_session.commit()
