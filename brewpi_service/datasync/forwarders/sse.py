import logging

from circuits import Component, handler

from brewpi_service.database import db_session, get_or_create
from brewpi_service.controller.models import Controller

from flask import Flask

app = Flask(__name__)
app.config["REDIS_URL"] = "redis://localhost"

from flask_sse import sse

from ..abstract import AbstractForwarder


LOGGER = logging.getLogger(__name__)


class SSEForwarder(Component, AbstractForwarder):
    """
    Notify SSE clients
    """
    @handler("ControllerConnected")
    def on_controller_appeared(self, event):
        LOGGER.debug("SSE: Controller Connected...")
        with app.app_context():
            sse.publish({"message": "connect"}, type='greeting')


    @handler("ControllerDisconnected")
    def on_controller_disappeared(self, event):
        LOGGER.debug("SSE: Controller disconnected...")
        with app.app_context():
            sse.publish({"message": "disconnect"}, type='greeting')

