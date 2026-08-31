"""Citire temperatura de la senzorii DS18B20 (1-Wire).

Necesita: pip install w1thermsensor, si 1-Wire activat pe Raspberry Pi
(raspi-config -> Interface Options -> 1-Wire).
"""

from dataclasses import dataclass


@dataclass
class TemperatureReading:
    sensor_id: str
    temperature_c: float


def read_all_sensors() -> list[TemperatureReading]:
    """Citeste toti senzorii DS18B20 conectati.

    TODO(Andreea): implementati cu w1thermsensor:
        from w1thermsensor import W1ThermSensor
        sensors = W1ThermSensor.get_available_sensors()
        return [TemperatureReading(s.id, s.get_temperature()) for s in sensors]
    Placeholder-ul de mai jos permite testare fara hardware conectat.
    """
    raise NotImplementedError("De implementat pe Raspberry Pi cu hardware conectat.")
