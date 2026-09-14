"""Buclă principală de execuție pe Raspberry Pi (Orchestrator IoT GraviTherm).

Citeste senzori -> publica MQTT & scrie InfluxDB -> inferenta RL (ONNX/Stub) -> comanda actuatoare
cu mecanism integrat Fail-Safe pentru oprire de siguranta.

Rulare: python -m gravitherm.iot.rpi_main
"""

from __future__ import annotations

import logging
import time

from gravitherm.config import PIPE_FLOW_REAL_BUILDING_L_S, PIPE_HEAD_REAL_BUILDING_M
from gravitherm.interfaces import Action, Observation
from gravitherm.iot.actuators.led import LedState, RGBLEDController
from gravitherm.iot.actuators.pump import PumpController
from gravitherm.iot.influx_writer import InfluxDBWriter
from gravitherm.iot.mqtt_client import GraviThermMQTTClient
from gravitherm.iot.sensors import bmp280, ds18b20
from gravitherm.simulation.env import hourly_energy_price
from gravitherm.simulation.hvac_profile import hvac_load_w
from gravitherm.simulation.pper_model import pper_power_w

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("GraviTherm_IoT")


def check_sensor_safety(utl_temp_c: float, pressure_bar: float) -> bool:
    """Verifică dacă măsurătorile senzorilor încadrează limitele fizice plauzibile.

    Parameters
    ----------
    utl_temp_c : float
        Temperatura măsurată a buclei UTL (°C).
    pressure_bar : float
        Presiunea măsurată pe conducta PPER (bar).

    Returns
    -------
    bool
        True dacă citirile sunt sigure [0°C - 50°C], False dacă s-a detectat o eroare critică.
    """
    if not (0.0 <= utl_temp_c <= 50.0):
        logger.error("ALERTĂ FAIL-SAFE: Temperatură UTL anormală detectată: %.2f °C", utl_temp_c)
        return False

    if not (0.0 <= pressure_bar <= 10.0):
        logger.error("ALERTĂ FAIL-SAFE: Presiune PPER anormală detectată: %.2f bar", pressure_bar)
        return False

    return True


class EnergyAwarePolicyStub:
    """Fallback inteligent pentru inferență RL pe Raspberry Pi când modelul ONNX nu este găsit."""

    def __init__(self) -> None:
        self._pump_on = False

    def act(self, obs: Observation) -> Action:
        temp = obs.utl_temperature_c
        price = obs.energy_price

        if price <= 0.3:
            if temp > 22.2:
                self._pump_on = True
            elif temp <= 21.8:
                self._pump_on = False
        elif price >= 0.8:
            if temp >= 23.8:
                self._pump_on = True
            elif temp <= 22.5:
                self._pump_on = False
        else:
            if temp >= 23.3:
                self._pump_on = True
            elif temp <= 22.0:
                self._pump_on = False

        return Action(pump_on=self._pump_on, pump_speed_pct=100.0 if self._pump_on else 0.0)


def main(loop_interval_s: float = 1.0) -> None:
    """Execută bucla principală de orchestrat IoT pe Raspberry Pi.

    Parameters
    ----------
    loop_interval_s : float
        Intervalul de timp în secunde între iterațiile de citire/comandă.
    """
    logger.info("Pornire modul orchestrator IoT GraviTherm pe Raspberry Pi...")

    # Conectare actuatoare, MQTT și InfluxDB
    pump = PumpController()
    led = RGBLEDController()
    mqtt_client = GraviThermMQTTClient()
    mqtt_client.connect()
    influx_writer = InfluxDBWriter()

    # Încărcare model inferență RL (PolicyRunner ONNX sau Fallback Stub)
    try:
        from gravitherm.agent.inference import PolicyRunner

        policy = PolicyRunner()
        logger.info("Model de inferență RL ONNX încărcat cu succes.")
    except (ImportError, OSError, RuntimeError, ValueError) as err:
        logger.warning(
            "Nu s-a putut încărca PolicyRunner ONNX (%s). Se folosește EnergyAwarePolicyStub.",
            err,
        )
        policy = EnergyAwarePolicyStub()

    step_count = 0

    try:
        while True:
            step_count += 1
            local_time = time.localtime()
            hour_of_day = float(local_time.tm_hour + local_time.tm_min / 60.0)

            # 1. Citire senzori hardware
            try:
                temp_readings = ds18b20.read_all_sensors()
                utl_temp = temp_readings[0].temperature_c if temp_readings else 22.0
            except (OSError, RuntimeError, IndexError, ValueError) as err:
                logger.error("Eroare la citirea senzorului DS18B20: %s", err)
                utl_temp = -999.0

            try:
                pressure_reading = bmp280.read_pressure()
                pper_pressure = pressure_reading.pressure_bar
            except (OSError, RuntimeError, ValueError) as err:
                logger.error("Eroare la citirea senzorului BMP280: %s", err)
                pper_pressure = -999.0

            # 2. Verificare protecție Fail-Safe
            if not check_sensor_safety(utl_temp_c=utl_temp, pressure_bar=pper_pressure):
                logger.critical("ACTIVARE STARE DE SIGURANȚĂ FAIL-SAFE! Oprire pompă...")
                pump.stop()
                led.blink(LedState.RED, on_time=0.3, off_time=0.3)

                mqtt_client.publish_actuator_state(
                    "failsafe",
                    {"status": "FAILSAFE_ACTIVE", "reason": "SENSOR_ERROR"},
                )
                influx_writer.write_point(
                    "alerts",
                    {"failsafe_active": 1.0},
                    tags={"type": "sensor_error"},
                )
                time.sleep(loop_interval_s)
                continue

            # 3. Calcul variabile de mediu
            calc_flow = PIPE_FLOW_REAL_BUILDING_L_S if pump.is_on else 0.0
            calc_head = PIPE_HEAD_REAL_BUILDING_M if pump.is_on else 0.0
            calc_pper_w = pper_power_w(flow_rate_l_s=calc_flow, head_m=calc_head)
            price_signal = hourly_energy_price(hour_of_day)
            hvac_w = hvac_load_w(hour_of_day=hour_of_day)

            # 4. Reconstruire obiect Observation conform interfaces.py
            obs = Observation(
                utl_temperature_c=utl_temp,
                pper_pressure_bar=pper_pressure,
                pper_power_w=calc_pper_w,
                hour_of_day=hour_of_day,
                energy_price=price_signal,
                hvac_load_w=hvac_w,
            )

            # 5. Inferență decizie RL
            try:
                action = policy.act(obs)
            except (RuntimeError, ValueError, TypeError) as err:
                logger.error("Eroare în inferența RL: %s. Se aplică decizia de siguranță.", err)
                action = Action(pump_on=False, pump_speed_pct=0.0)

            # 6. Comandă actuatoare (Pompă & LED)
            pump.apply(action)

            if action.pump_on:
                led.set_state(LedState.GREEN)
            else:
                led.set_state(LedState.BLUE)

            # 7. Publicare mesaje MQTT conform interfaces.py
            mqtt_client.publish_sensor_reading("temp1", utl_temp, "C")
            mqtt_client.publish_sensor_reading("pressure", pper_pressure, "bar")
            mqtt_client.publish_actuator_state("pump", pump.to_telemetry_message())
            mqtt_client.publish_actuator_state("led", led.to_telemetry_message())

            # 8. Scriere serii temporale în InfluxDB
            influx_writer.write_point(
                "sensor_readings",
                {
                    "utl_temperature_c": utl_temp,
                    "pper_pressure_bar": pper_pressure,
                    "pper_power_w": calc_pper_w,
                    "hvac_load_w": hvac_w,
                    "energy_price": price_signal,
                },
                tags={"device": "raspberry_pi_4"},
            )
            influx_writer.write_point(
                "actuator_states",
                {
                    "pump_on": 1.0 if action.pump_on else 0.0,
                    "pump_speed_pct": float(action.pump_speed_pct),
                },
                tags={"device": "l298n_driver"},
            )

            if step_count % 10 == 0:
                logger.info(
                    "Pas %d: T_UTL=%.2f°C, P_PPER=%.2f W, Tarif=%.2f, Pompă=%s (%.0f%%)",
                    step_count,
                    utl_temp,
                    calc_pper_w,
                    price_signal,
                    "ON" if action.pump_on else "OFF",
                    action.pump_speed_pct,
                )

            time.sleep(loop_interval_s)

    except KeyboardInterrupt:
        logger.info("Oprire cerută de utilizator (Ctrl+C). Dezactivare actuatoare...")
    finally:
        pump.stop()
        led.off()
        mqtt_client.disconnect()
        influx_writer.close()
        logger.info("Resurse eliberate. Sistem Oprit.")


if __name__ == "__main__":
    main()
