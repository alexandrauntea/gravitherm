"""Consuma mesaje MQTT si le scrie in InfluxDB (time-series)."""


def write_point(measurement: str, value: float, tags: dict | None = None) -> None:
    """TODO(Andreea): implementati cu influxdb-client:
        from influxdb_client import InfluxDBClient, Point
        client = InfluxDBClient(url=INFLUXDB_URL, token=..., org=INFLUXDB_ORG)
        write_api = client.write_api()
        point = Point(measurement).field("value", value)
        write_api.write(bucket=INFLUXDB_BUCKET, record=point)
    Token-ul InfluxDB vine din variabila de mediu (.env), niciodata hardcodat.
    """
    raise NotImplementedError("De implementat cu influxdb-client.")
