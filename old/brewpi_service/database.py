import logging

from sqlalchemy import create_engine, Column
from sqlalchemy.orm import scoped_session, sessionmaker, mapper, composite
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.ext.declarative import declarative_base, DeclarativeMeta
from sqlalchemy.exc import IntegrityError

from flask_plugins import emit_event

from brewpi_service import app

LOGGER = logging.getLogger(__name__)

engine = create_engine(app.config['DATABASE_URI'], convert_unicode=True)
db_session = scoped_session(sessionmaker(autocommit=False,
                                         autoflush=False,
                                         bind=engine))


@app.teardown_appcontext
def shutdown_session(exception=None):
    db_session.remove()

from collections import UserList


class ControllerCompositeColumn(object):
    def __init__(self, actual_column, requested_column):
        self.actual_column = actual_column
        self.requested_column = requested_column

    def __composite_values__(self):
        return self.actual_column, self.requested_column

from brewpi_service.controller.state import ControllerDataField
class BaseClsMeta(DeclarativeMeta):
    def __init__(cls, classname, bases, dict_):
        cls._controller_data_fields = []

        for name, attribute in cls.__dict__.items():
            if type(attribute) is ControllerDataField:
                LOGGER.debug("Marking attribute '{0}' as controller state".format(name))
                cls._controller_data_fields.append(name)

        return super(BaseClsMeta, cls).__init__(classname, bases, dict_)


Base = declarative_base(metaclass=BaseClsMeta, mapper=mapper)
Base.query = db_session.query_property()


def load_models():
    from .controller import models # NOQA
    emit_event('load-database-models')


def init_db():
    """
    import all modules here that might define models so that
    they will be registered properly on the metadata.  Otherwise
    you will have to import them first before calling init_db()
    """
    Base.metadata.create_all(bind=engine)


def get_or_create(session,
                  model,
                  create_method='',
                  create_method_kwargs=None,
                  **kwargs):
    """
    Shortcut to get or create an object
    """
    try:
        return session.query(model).filter_by(**kwargs).one(), False
    except NoResultFound:
        kwargs.update(create_method_kwargs or {})
        created = getattr(model, create_method, model)(**kwargs)
        try:
            session.add(created)
            session.commit()
            return created, True
        except IntegrityError as e:
            session.rollback()
            LOGGER.error(e)
            return session.query(model).filter_by(**kwargs).one(), True
