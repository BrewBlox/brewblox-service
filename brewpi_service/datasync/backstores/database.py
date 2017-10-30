import logging

from circuits import Component, handler

from sqlalchemy.exc import IntegrityError

from sqlalchemy.orm import scoped_session, sessionmaker

from brewpi_service.database import engine, get_or_create, db_session
from brewpi_service.controller.models import Controller
from brewpi_service.controller.models import ControllerBlock

from ..abstract import AbstractBackstoreSyncher


LOGGER = logging.getLogger(__name__)


class DatabaseSyncher(Component, AbstractBackstoreSyncher):
    """
    Synchronize backend events to a Database using SQLAlchemy
    """

    def init(self):
        self.session = scoped_session(sessionmaker(autocommit=False,
                                                   autoflush=False,
                                                   bind=engine))

    @handler("started")
    def started(self, *args):
        # Mark all controllers as disconnected
        self.session.query(Controller).update({Controller.connected: False})
        self.session.commit()

    @handler("ControllerConnected")
    def on_controller_appeared(self, event):
        aController = event.controller

        controller, created = get_or_create(self.session, Controller,
                                            create_method_kwargs={'name': aController.name,
                                                                  'description': aController.description,
                                                                  'connected': True,
                                                                  'profile_id': aController.profile.id},
                                            uri=aController.uri)

        if created is False:
            LOGGER.debug("Controller has reconnected: {0}".format(controller))
        else:
            LOGGER.debug("New Controller connected: {0}".format(controller))

        controller.connected = True

        self.session.commit()


    @handler("ControllerDisconnected")
    def on_controller_disappeared(self, event):
        aController = event.controller

        LOGGER.debug("Controller disconnected: {0}".format(aController.uri))
        controller = self.session.query(Controller).filter(Controller.uri == aController.uri).first()
        controller.connected = False

        db_session.commit()


    @handler("ControllerBlockList")
    def on_controller_block_list(self, event):
        LOGGER.debug("Synching {0} blocks from controller {1}".format(len(event.blocks), event.controller))

        db_controller = db_session.query(Controller).filter(Controller.uri==event.controller.uri).first()

        if db_controller is None:
            LOGGER.error("Got list of blocks for an unknown controller, aborting.")
            return # FIXME

        for block in event.blocks:
            # Check if we already have a block of this ID
            existing_block = db_session.query(ControllerBlock).filter(ControllerBlock.profile_id==block.profile.id,
                                                                      ControllerBlock.object_id==block.object_id).first()

            if existing_block is not None:
                # Check we have the same type in DB as we have in controller's memory
                typed_block = db_session.query(type(block)).filter(ControllerBlock.profile_id==block.profile.id,
                                                                   ControllerBlock.object_id==block.object_id).one()

                if typed_block is None:
                    # FIXME: Type mismatch, what should we do?
                    LOGGER.error("Type mismatch between Controller and Database, fix that by hand!")
            else:
                try:
                    LOGGER.debug("Adding block :{0}".format(block))
                    db_session.add(block)
                    db_session.commit()
                except IntegrityError as e:
                    db_session.rollback()
                    LOGGER.error(e)

                LOGGER.debug("New object synched from controller memory: {0}".format(block))
