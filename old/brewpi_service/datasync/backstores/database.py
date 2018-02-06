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
                                                                  'profile_id': aController.profile_id},
                                            uri=aController.uri)

        if created is False:
            LOGGER.debug("Controller has reconnected: {0}".format(controller))
            controller.connected = True

            self._wipe_available_blocks_for(controller.profile, self.session)

        else:
            LOGGER.debug("New Controller connected: {0}".format(controller))


        self.session.commit()

    def _wipe_available_blocks_for(self, aControllerProfile, aDBSession):
        """
        Remove all available blocks
        """
        aDBSession.query(ControllerBlock).filter(ControllerBlock.profile_id==aControllerProfile.id,
                                                 ControllerBlock.is_static==False).delete(synchronize_session=False)

    def _clean_stale_available_blocks_for(self, aControllerProfile, time_limit, aDBSession):
        """
        Remove all stale available blocks (not updated since a few seconds)
        """
        aDBSession.query(ControllerBlock).filter(ControllerBlock.profile_id==aControllerProfile.id,
                                                 ControllerBlock.is_static==False,
                                                 ControllerBlock.updated_at<=time_limit).delete(synchronize_session=False)

    @handler("ControllerDisconnected")
    def on_controller_disappeared(self, event):
        aController = event.controller

        LOGGER.debug("Controller disconnected: {0}".format(aController.uri))
        controller = db_session.query(Controller).filter(Controller.uri==aController.uri).first()
        controller.connected = False

        self._wipe_available_blocks_for(controller.profile, db_session)

        db_session.commit()

    @handler("ControllerCleanStaleAvailableBlocks")
    def on_clean_stale_available_blocks(self, event):
        LOGGER.debug("Cleaning Stale Available Blocks for controller {0}".format(event.controller))

        controller = db_session.query(Controller).filter(Controller.uri==event.controller.uri).first()
        self._clean_stale_available_blocks_for(controller.profile, event.time_limit, db_session)
        db_session.flush()

    @handler("ControllerBlockList") ## Disabled while working on available blocks
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

                # just mark it updated
                from datetime import datetime
                existing_block.updated_at = datetime.utcnow()
                db_session.add(existing_block)
            else:
                LOGGER.debug("Adding block :{0}".format(block))
                db_session.add(block)

                LOGGER.debug("New object synched from controller memory: {0}".format(block))

        try:
            db_session.commit()
        except IntegrityError as e:
            db_session.rollback()
            LOGGER.error(e)

