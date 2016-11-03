from sqlalchemy import Column, Integer, String, Boolean
from ..database import Base


class Controller(Base):
    """
    A Hardware Controller that holds sensors and actuators
    """
    __tablename__ = 'controllers'

    id = Column(Integer, primary_key=True)
    name = Column(String(64), index=True, unique=True)
    uri = Column(String(128), index=True, unique=True)
    description = Column(String(128))
    alive = Column(Boolean)

    def __repr__(self):
        return '<Controller {0} - {1}>'.format(self.name, self.uri)
