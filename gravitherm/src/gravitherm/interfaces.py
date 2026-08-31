"""Contractul comun între module (simulation / agent / iot).

Acest fișier este GRANIȚA dintre cele 3 module deținute de persoane diferite.
Orice schimbare aici trebuie discutată cu toată echipa înainte de commit
(vezi CONTRIBUTING.md). Nu adăugați logică de business aici — doar forma
datelor care circulă între module.

TODO (echipă, ziua 1): confirmați împreună fiecare câmp de mai jos înainte
de a începe implementarea modulelor. Valorile/unitățile sunt propuneri de
pornire, nu decizii finale.
"""

from dataclasses import dataclass


@dataclass
class Observation:
    """Ce vede agentul RL la fiecare pas (simulat SAU real).

    Câmpurile trebuie populate identic de simulation/env.py (date sintetice)
    și de iot/rpi_main.py (date reale de la senzori), ca agent/inference.py
    să nu observe nicio diferență între cele două surse.
    """

    utl_temperature_c: float      # temperatura buclei UTL, °C
    pper_pressure_bar: float      # presiunea pe conducta PPER, bar
    pper_power_w: float           # puterea instantanee estimată PPER, W
    hour_of_day: float            # 0.0-23.99, pentru semnalul de tarif orar
    energy_price: float           # tarif orar normalizat 0.0-1.0 (1.0 = varf)
    hvac_load_w: float            # consumul HVAC curent simulat/estimat, W


@dataclass
class Action:
    """Decizia agentului: comanda pentru pompa de circulație UTL."""

    pump_on: bool
    pump_speed_pct: float  # 0-100, folosit doar dacă driverul suportă PWM


@dataclass
class RewardBreakdown:
    """Termenii funcției de recompensă (Ecuația 1 din propunere), separați
    pentru a putea fi loghați/vizualizați individual în dashboard."""

    comfort: float
    recaptured_energy_bonus: float
    price_bonus: float
    grid_penalty: float
    discomfort_penalty: float

    @property
    def total(self) -> float:
        return (
            self.comfort
            + self.recaptured_energy_bonus
            + self.price_bonus
            - self.grid_penalty
            - self.discomfort_penalty
        )


# --- Contractul MQTT (folosit de iot/mqtt_client.py și influx_writer.py) ---
#
# Topic-uri (prefix comun "gravitherm/"):
#   gravitherm/sensors/temp1|temp2|temp3   -> DS18B20, payload: SensorMessage
#   gravitherm/sensors/pressure             -> BMP280, payload: SensorMessage
#   gravitherm/actuators/pump               -> comanda curentă a pompei
#   gravitherm/actuators/led                -> starea LED-ului
#
# Payload JSON (SensorMessage): {"timestamp": ISO8601, "value": float, "unit": str}
