from datetime import datetime


class InfluxMeasurementWriter:
    """
    Utilitary class to ease writing measures to Influx
    """
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
