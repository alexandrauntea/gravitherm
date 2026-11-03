"""Modul pentru consumarea seriilor temporale și scrierea lor în InfluxDB OSS."""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime

from gravitherm.config import INFLUXDB_BUCKET, INFLUXDB_ORG, INFLUXDB_URL

logger = logging.getLogger(__name__)

# Preluare setări din variabilele de mediu (.env) cu valori fallback din config.py
URL = os.getenv("INFLUXDB_URL", INFLUXDB_URL)
ORG = os.getenv("INFLUXDB_ORG", INFLUXDB_ORG)
BUCKET = os.getenv("INFLUXDB_BUCKET", INFLUXDB_BUCKET)
TOKEN = os.getenv("INFLUXDB_TOKEN", "gravitherm-dev-token")


class InfluxDBWriter:
    """Gestionar pentru conexiunea InfluxDB și scrierea punctelor time-series."""

    def __init__(
        self,
        url: str = URL,
        token: str = TOKEN,
        org: str = ORG,
        bucket: str = BUCKET,
    ) -> None:
        """Inițializează clientul InfluxDB și API-ul de scriere.

        Parameters
        ----------
        url : str
            URL-ul serverului InfluxDB (ex: http://localhost:8086).
        token : str
            Token-ul de autentificare InfluxDB (stocat în .env).
        org : str
            Numele organizației InfluxDB.
        bucket : str
            Numele bucket-ului în care se salvează datele.
        """
        self.url = url
        self.token = token
        self.org = org
        self.bucket = bucket

        self._client = None
        self._write_api = None
        self.is_connected = False

        try:
            from influxdb_client import InfluxDBClient  # type: ignore[import-untyped]
            from influxdb_client.client.write_api import SYNCHRONOUS  # type: ignore[import-untyped]

            self._client = InfluxDBClient(url=url, token=token, org=org)
            self._write_api = self._client.write_api(write_options=SYNCHRONOUS)
            self.is_connected = True
            logger.info("Client InfluxDB conectat la %s (bucket=%s)", url, bucket)
        except (ImportError, OSError, RuntimeError, ValueError, AttributeError) as err:
            logger.warning(
                "Conectare la InfluxDB indisponibilă (%s). Scrierea se va executa în mod silent fallback.",
                err,
            )
            self.is_connected = False

    def write_point(
        self,
        measurement: str,
        fields: dict[str, float | int | bool | str],
        tags: dict[str, str] | None = None,
        timestamp: datetime | None = None,
    ) -> bool:
        """Scrie un punct de măsurătoare în InfluxDB.

        Parameters
        ----------
        measurement : str
            Numele măsurătorii (ex: "temperature", "pressure", "actuator_pump").
        fields : dict[str, float | int | bool | str]
            Câmpurile numerice/string ale măsurătorii (ex: {"value": 22.5}).
        tags : dict[str, str] | None
            Etichete opționale de filtrare (ex: {"location": "utl_loop"}).
        timestamp : datetime | None
            Timestamp UTC opțional. Implicit folosește timpul curent.

        Returns
        -------
        bool
            True dacă scrierea a fost reușită, False în caz contrar.
        """
        if not self.is_connected or self._write_api is None:
            return False

        try:
            from influxdb_client import Point  # type: ignore[import-untyped]

            point = Point(measurement)
            if tags:
                for k, v in tags.items():
                    point.tag(k, v)

            for field_key, field_value in fields.items():
                point.field(field_key, field_value)

            if timestamp is not None:
                point.time(timestamp)
            else:
                point.time(datetime.now(UTC))

            self._write_api.write(bucket=self.bucket, record=point)
            return True
        except (OSError, RuntimeError, ValueError, AttributeError) as err:
            logger.error("Eroare la scrierea punctului %s în InfluxDB: %s", measurement, err)
            return False

    def close(self) -> None:
        """Închide conexiunea InfluxDB."""
        if self._client is not None:
            try:
                self._client.close()
            except (OSError, RuntimeError, AttributeError) as err:
                logger.debug("Eroare închidere client InfluxDB: %s", err)
            self.is_connected = False


_DEFAULT_WRITER: InfluxDBWriter | None = None


def write_point(measurement: str, value: float, tags: dict[str, str] | None = None) -> None:
    """Funcție utilitară globală pentru scrierea rapidă a unei valori în InfluxDB.

    Parameters
    ----------
    measurement : str
        Numele măsurătorii (ex: "temperature").
    value : float
        Valoarea măsurată.
    tags : dict[str, str] | None
        Etichete opționale.
    """
    global _DEFAULT_WRITER
    if _DEFAULT_WRITER is None:
        _DEFAULT_WRITER = InfluxDBWriter()
    _DEFAULT_WRITER.write_point(measurement, fields={"value": float(value)}, tags=tags)
