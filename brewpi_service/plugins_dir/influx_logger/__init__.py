import logging

from influxdb import InfluxDBClient, SeriesHelper

from brewpi_service.plugins.core import BrewPiServicePlugin
from brewpi_service.database import db_session, get_or_create
from brewpi_service.admin import admin, ModelView

from .models import LoggedDeviceConfiguration
from .utils import InfluxMeasurementWriter

__plugin__ = "InfluxLoggerPlugin"

LOGGER = logging.getLogger(__name__)


class InfluxLoggerPlugin(BrewPiServicePlugin):
    """
    Log any model property to influxdb time series
    """
    def __init__(self, *args, **kwargs):
        self.client = None

        super(InfluxLoggerPlugin, self).__init__(*args, **kwargs)

    def log_data_before_update(self, mapper, connection, target):
        """
        Callback when an object is about to be saved: log its data if a
        `LoggedDeviceConfiguration` matches.
        """
        logging_configuration = db_session.query(LoggedDeviceConfiguration).filter(LoggedDeviceConfiguration.device_id==target.id).one()
        if not logging_configuration:
            return

        writer = InfluxMeasurementWriter(self.client, measurement='object_{0}'.format(logging_configuration.device_id))

        # XXX Should support multiple fields
        field = logging_configuration.device_field
        writer.write({field: getattr(target, field)})

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

