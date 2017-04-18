from flask_apispec import FlaskApiSpec
from flask_restful import Api

from brewpi_service import app

specs = FlaskApiSpec(app)

api = Api()
