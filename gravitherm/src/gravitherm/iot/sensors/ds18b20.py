"""Citire temperatură de la senzorii DS18B20 (1-Wire).

Necesită: pip install w1thermsensor, și 1-Wire activat pe Raspberry Pi
(raspi-config -> Interface Options -> 1-Wire).
Include suport de fallback (mock) pentru testare pe laptop/CI.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class TemperatureReading:
    sensor_id: str
    temperature_c: float


def read_all_sensors() -> list[TemperatureReading]:
    """Citește toți senzorii DS18B20 conectați pe magistrala 1-Wire.

    Dacă librăria w1thermsensor nu este instalată sau nu sunt detectați senzori
    fizici pe magistrală, returnează date sintetice de fallback (mock).

    Returns
    -------
    list[TemperatureReading]
        Lista de citiri de temperatură pentru fiecare senzor detectat.
    """
    try:
        from w1thermsensor import W1ThermSensor  # type: ignore[import-untyped]

        sensors = W1ThermSensor.get_available_sensors()
        if sensors:
            return [
                TemperatureReading(
                    sensor_id=str(sensor.id),
                    temperature_c=float(sensor.get_temperature()),
                )
                for sensor in sensors
            ]
    except Exception as err:  # noqa: BLE001
        logger.debug("Senzor DS18B20 indisponibil fizic, se folosește mock: %s", err)

    # Fallback mock pentru mediu de dezvoltare / laptop
    return [
        TemperatureReading(sensor_id="ds18b20_mock_utl", temperature_c=22.5),
    ]
