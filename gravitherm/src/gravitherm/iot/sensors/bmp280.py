"""Citire presiune/temperatură de la senzorul BMP280 (I2C).

Necesită: pip install adafruit-circuitpython-bmp280, I2C activat pe RPi.
Include suport de fallback (mock) pentru testare pe laptop/CI.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class PressureReading:
    pressure_bar: float
    temperature_c: float


def read_pressure() -> PressureReading:
    """Citește presiunea și temperatura de la senzorul I2C BMP280.

    Dacă senzorul nu este conectat sau librăriile adafruit/board nu sunt
    disponibile, returnează valorile implicite de laborator (1.013 bar, 22.5°C).

    Returns
    -------
    PressureReading
        Obiect ce conține presiunea măsurată în bar și temperatura în °C.
    """
    try:
        import adafruit_bmp280  # type: ignore[import-untyped]
        import board  # type: ignore[import-untyped]

        i2c = board.I2C()
        sensor = adafruit_bmp280.Adafruit_BMP280_I2C(i2c)
        return PressureReading(
            pressure_bar=float(sensor.pressure / 1000.0),
            temperature_c=float(sensor.temperature),
        )
    except Exception as err:  # noqa: BLE001
        logger.debug("Senzor BMP280 indisponibil fizic, se folosește mock: %s", err)

    # Fallback mock pentru mediu de dezvoltare / laptop
    return PressureReading(pressure_bar=1.013, temperature_c=22.5)
