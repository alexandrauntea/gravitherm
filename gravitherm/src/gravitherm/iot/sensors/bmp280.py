"""Citire presiune/temperatura de la BMP280 (I2C).

Necesita: pip install adafruit-circuitpython-bmp280, I2C activat pe RPi.
"""

from dataclasses import dataclass


@dataclass
class PressureReading:
    pressure_bar: float
    temperature_c: float


def read_pressure() -> PressureReading:
    """TODO(Andreea): implementati cu adafruit_bmp280:
        import board, adafruit_bmp280
        i2c = board.I2C()
        sensor = adafruit_bmp280.Adafruit_BMP280_I2C(i2c)
        return PressureReading(sensor.pressure / 1000, sensor.temperature)
    """
    raise NotImplementedError("De implementat pe Raspberry Pi cu hardware conectat.")
