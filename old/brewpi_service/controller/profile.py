import logging
from sqlalchemy.sql import exists
from sqlalchemy.orm.exc import NoResultFound

from ..database import db_session

from .models import ControllerProfile

LOGGER = logging.getLogger(__name__)


class ControllerProfileManager:
    def get(self, name):
        return db_session.query(ControllerProfile).filter(ControllerProfile.name==name).one()

    def exists(self, name):
        return db_session.query(ControllerProfile).filter(exists().where(ControllerProfile.name==name)).first()

    def create(self, name):
        new_profile = ControllerProfile(name=name)
        db_session.add(new_profile)
        db_session.commit()
        LOGGER.debug("Created new profile {0}".format(name))

        return new_profile



ControllerProfileManager = ControllerProfileManager()

