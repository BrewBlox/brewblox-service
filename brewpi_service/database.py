from flask_plugins import emit_event
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.ext.declarative import declarative_base


engine = create_engine('sqlite:///brewpi-service.db', convert_unicode=True)
db_session = scoped_session(sessionmaker(autocommit=False,
                                         autoflush=False,
                                         bind=engine))

Base = declarative_base()
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
        return session.query(model).filter_by(**kwargs).one(), True
    except NoResultFound:
        kwargs.update(create_method_kwargs or {})
        created = getattr(model, create_method, model)(**kwargs)
        try:
            session.add(created)
            session.commit()
            return created, False
        except IntegrityError:
            session.rollback()
            return session.query(model).filter_by(**kwargs).one(), True
