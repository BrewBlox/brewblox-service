import logging

from basicevents import subscribe

from brewpi_service.database import db_session, get_or_create
from brewpi_service.controller.models import Controller

from flask import Flask

app = Flask(__name__)
app.config["REDIS_URL"] = "redis://localhost"

from flask_sse import sse

from ..abstract import AbstractForwarder


LOGGER = logging.getLogger(__name__)


class SSEForwarder(AbstractForwarder):
    """
    Notify SSE clients
    """
    @staticmethod
    @subscribe("controller.connected")
    def on_controller_appeared(aController):
        print("SSE...")
        with app.app_context():
            sse.publish({"message": "connect"}, type='greeting')


    @staticmethod
    @subscribe("controller.disconnected")
    def on_controller_disappeared(aController):
        print("SSE out...")
        with app.app_context():
            sse.publish({"message": "disconnect"}, type='greeting')

