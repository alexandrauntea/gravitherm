"""Bucla principala de pe Raspberry Pi - Faza III/IV (bucla inchisa).

Citeste senzori -> publica MQTT -> obtine decizia agentului -> comanda actuatoare.
Punct de intrare: python -m gravitherm.iot.rpi_main
"""

import time

from gravitherm.agent.inference import PolicyRunner
from gravitherm.interfaces import Observation
from gravitherm.iot.actuators.pump import PumpController
from gravitherm.iot.sensors import bmp280, ds18b20


def main(loop_interval_s: float = 5.0):
    policy = PolicyRunner()
    pump = PumpController()

    while True:
        # TODO(Andreea): inlocuiti cu citiri reale + publicare MQTT.
        temp_readings = ds18b20.read_all_sensors()
        pressure = bmp280.read_pressure()

        obs = Observation(
            utl_temperature_c=temp_readings[0].temperature_c,
            pper_pressure_bar=pressure.pressure_bar,
            pper_power_w=0.0,  # TODO: calculati din presiune, vezi simulation/pper_model.py
            hour_of_day=time.localtime().tm_hour,
            energy_price=0.5,  # TODO: sursa reala de tarif orar, daca e disponibila
            hvac_load_w=0.0,
        )

        action = policy.act(obs)
        pump.apply(action)

        time.sleep(loop_interval_s)


if __name__ == "__main__":
    main()
