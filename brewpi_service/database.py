from sqlalchemy import create_engine, Column
from sqlalchemy.orm import scoped_session, sessionmaker, mapper, composite
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.ext.declarative import declarative_base, DeclarativeMeta

from flask_plugins import emit_event

from brewpi_service import app


engine = create_engine('sqlite:///brewpi-service.db', convert_unicode=True)
db_session = scoped_session(sessionmaker(autocommit=False,
                                         autoflush=False,
                                         bind=engine))


@app.teardown_appcontext
def shutdown_session(exception=None):
    db_session.remove()

class ControllerData(object):
    def __init__(self, *args, **kwargs):
        self._writable = False

        if 'writable' in kwargs:
            self._writable = True
            kwargs.pop('writable')

        self._args = args
        self._kwargs = kwargs


class ControllerCompositeColumn(object):
    def __init__(self, actual_column, requested_column):
        self.actual_column = actual_column
        self.requested_column = requested_column

    def __composite_values__(self):
        return self.actual_column, self.requested_column


class BaseClsMeta(DeclarativeMeta):
    def __init__(cls, classname, bases, dict_):

        new_fields = {}
        for name, attribute in dict_.items():
            if type(attribute) is ControllerData:
                if attribute._writable:
                    requested_colname = "_{0}_requested".format(name)
                    requested_column = Column(requested_colname, *attribute._args, nullable=True, **attribute._kwargs)
                    new_fields[requested_colname] = requested_column

                    actual_colname = "_{0}".format(name)
                    actual_column = Column(actual_colname, *attribute._args, nullable=True, **attribute._kwargs)
                    new_fields[actual_colname] = actual_column

                    composite_colname = "{0}".format(name)
                    new_fields[composite_colname] = composite(ControllerCompositeColumn,
                                                              actual_column,
                                                              requested_column)
                else:
                    new_fields[name] = Column(name, *attribute._args, **attribute._kwargs)

        # Set new fields
        dict_.update(new_fields)
        for new_field_name, new_field in new_fields.items():
            setattr(cls, new_field_name, dict_[new_field_name])

        super(BaseClsMeta, cls).__init__(classname, bases, dict_)


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
        except IntegrityError:
            session.rollback()
            return session.query(model).filter_by(**kwargs).one(), True
