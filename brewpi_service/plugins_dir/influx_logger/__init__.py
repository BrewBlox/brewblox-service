from datetime import datetime
import logging

from brewpi_service.plugins.core import BrewPiServicePlugin
from brewpi_service.database import db_session, get_or_create
from brewpi_service.admin import admin, ModelView

from influxdb import InfluxDBClient, SeriesHelper

__plugin__ = "InfluxLoggerPlugin"

LOGGER = logging.getLogger(__name__)

class InfluxMeasurementWriter:
    def __init__(self, influx_client, measurement):
        self.client = influx_client
        self.measurement = measurement

    def write(self, fields):
        json_body = self._to_json(fields)
        self.client.write_points(json_body)
        return True

    def _to_json(self, fields):
        json_body = [
            {
                "measurement": self.measurement,
                "time": datetime.utcnow(),
                "fields": fields
            }
        ]

        return json_body


class InfluxLoggerPlugin(BrewPiServicePlugin):
    """
    Log any model property to influxdb time series
    """
    def __init__(self, *args, **kwargs):
        self.client = None

        super(InfluxLoggerPlugin, self).__init__(*args, **kwargs)


    def log_data_before_update(self, mapper, connection, target):
        # execute a stored procedure upon INSERT,
        # apply the value to the row to be inserted
        writer = InfluxMeasurementWriter(self.client, measurement='test')
        writer.write({'value': 39})


    def setup(self):
        from .models import LoggedDeviceConfiguration

    def install(self):
        # Admin
        from .admin import LoggedDeviceConfigurationAdminView

        self.client = InfluxDBClient('localhost', 8086, 'root', 'root', 'brewpi')
        self.client.create_database('brewpi')
        self.client.switch_database('brewpi')

        from .models import LoggedDeviceConfiguration

        from sqlalchemy import event

        # for configuration in db_session.query(LoggedDeviceConfiguration):
        #    event.listen(configuration.device.__class__, 'before_update', self.log_data_before_update)

