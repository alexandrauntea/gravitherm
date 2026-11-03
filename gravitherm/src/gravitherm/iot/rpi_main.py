"""Buclă principală de execuție pe Raspberry Pi (Orchestrator IoT GraviTherm).

Citește senzori -> publică MQTT & scrie InfluxDB -> inferență RL (ONNX/Stub) -> comandă actuatoare
cu mecanism integrat Fail-Safe pentru oprire de siguranță.

Rulare: python -m gravitherm.iot.rpi_main [--simulated] [--max-loops N] [--model-path PATH]
"""

from __future__ import annotations

import argparse
import logging
import time
from datetime import UTC, datetime

from gravitherm.config import (
    HOT_SIDE_LIMIT_C,
    HOT_SIDE_WARN_C,
    ONNX_MODEL_PATH,
    PIPE_FLOW_REAL_BUILDING_L_S,
    PIPE_HEAD_REAL_BUILDING_M,
)
from gravitherm.interfaces import Action, Observation
from gravitherm.iot.actuators.led import LedState, RGBLEDController
from gravitherm.iot.actuators.peltier import PeltierController
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


def check_peltier_thermal_safety(hot_side_temp_c: float | None) -> tuple[bool, str]:
    """Verifică dacă radiatorul/partea caldă a modulului Peltier este în limite sigure.

    Parameters
    ----------
    hot_side_temp_c : float | None
        Temperatura măsurată pe partea caldă a Peltier-ului (°C).

    Returns
    -------
    tuple[bool, str]
        (is_safe, message)
    """
    if hot_side_temp_c is None:
        return (
            False,
            f"[SAFETY] Senzorul cald Peltier ({ds18b20.DS18B20_HOT_SIDE}) este DECONECTAT sau returnează eroare! Oprire de urgență Peltier.",
        )

    if hot_side_temp_c >= HOT_SIDE_LIMIT_C:
        return (
            False,
            f"[SAFETY] Temperatură CRITICĂ radiator Peltier detectată: {hot_side_temp_c:.2f}°C >= limită {HOT_SIDE_LIMIT_C:.1f}°C! Risc iminent de delaminare! Tăiere alimentare Peltier!",
        )

    if hot_side_temp_c >= HOT_SIDE_WARN_C:
        logger.warning(
            "[WARNING] Temperatură ridicată radiator Peltier: %.2f°C >= prag avertizare %.1f°C",
            hot_side_temp_c,
            HOT_SIDE_WARN_C,
        )

    return True, "OK"


def read_sensor_observation(
    simulated: bool = False,
) -> tuple[float, float, dict[str, float | None]]:
    """Citește senzorii hardware mapați (DS18B20 & BMP280) sau folosește valori simulate.

    Sursa principală de temperatură pentru bucla UTL (apa clădirii) este senzorul REZERVOR (28-0000006e6d0e).
    Senzorul COLD_SIDE monitorizează partea rece ("solul" UTL).
    Senzorul HOT_SIDE monitorizează radiatorul cald STRICT pentru siguranță termică.

    Returns
    -------
    tuple[float, float, dict[str, float | None]]
        - utl_temp: temperatura apei din rezervor (°C)
        - pper_pressure: presiunea conductei (bar)
        - mapped_temps: dicționar cu toate cele 3 temperaturi mapate {'reservoir', 'cold_side', 'hot_side'}
    """
    if simulated:
        return 22.5, 1.2, {"reservoir": 22.5, "cold_side": 13.0, "hot_side": 28.0}

    mapped_temps = ds18b20.read_mapped_temperatures()
    utl_temp = mapped_temps.get("reservoir")
    if utl_temp is None:
        logger.warning(
            "Senzorul REZERVOR (%s) nu a putut fi citit; se folosește valoare fallback 22.0°C",
            ds18b20.DS18B20_RESERVOIR,
        )
        utl_temp = 22.0

    try:
        pressure_reading = bmp280.read_pressure()
        pper_pressure = pressure_reading.pressure_bar
    except Exception as err:
        logger.warning("Eroare la citirea senzorului BMP280 (%s), se folosește fallback 1.013 bar", err)
        pper_pressure = 1.013

    return utl_temp, pper_pressure, mapped_temps


def run_control_loop(
    model_path: str = ONNX_MODEL_PATH,
    loop_interval_s: float = 1.0,
    simulated: bool = False,
    max_loops: int | None = None,
) -> None:
    """Execută bucla principală de orchestrat IoT pe Raspberry Pi."""
    logger.info("Pornire modul orchestrator IoT GraviTherm pe Raspberry Pi...")

    pump = PumpController()
    peltier = PeltierController()
    led = RGBLEDController()

    mqtt_client: GraviThermMQTTClient | None = None
    try:
        mqtt_client = GraviThermMQTTClient()
        mqtt_client.connect()
    except Exception as err:
        logger.warning("Conectare MQTT eșuată (%s). Se continuă fără broker MQTT.", err)
        mqtt_client = None

    influx_writer: InfluxDBWriter | None = None
    try:
        influx_writer = InfluxDBWriter()
    except Exception as err:
        logger.warning("Inițializare InfluxDB eșuată (%s). Se continuă fără InfluxDB.", err)
        influx_writer = None

    # Încărcare model inferență RL (PolicyRunner ONNX sau Fallback Stub)
    try:
        from gravitherm.agent.inference import PolicyRunner

        policy = PolicyRunner(model_path=model_path)
        logger.info("Model de inferență RL ONNX (%s) încărcat cu succes.", model_path)
    except Exception as err:
        logger.warning(
            "Nu s-a putut încărca PolicyRunner ONNX (%s). Se folosește EnergyAwarePolicyStub.",
            err,
        )
        policy = EnergyAwarePolicyStub()

    step_count = 0

    try:
        while True:
            step_count += 1
            now = datetime.now(UTC)
            hour_of_day = float(now.hour + now.minute / 60.0)

            # 1. Citire senzori hardware/simulați (mapare pe roluri specifice)
            utl_temp, pper_pressure, mapped_temps = read_sensor_observation(simulated=simulated)
            cold_temp = mapped_temps.get("cold_side")
            hot_temp = mapped_temps.get("hot_side")

            # 2a. Verificare protecție Fail-Safe generală (UTL & Presiune)
            if not check_sensor_safety(utl_temp_c=utl_temp, pressure_bar=pper_pressure):
                logger.critical("ACTIVARE STARE DE SIGURANȚĂ FAIL-SAFE! Oprire pompă și Peltier...")
                try:
                    pump.stop()
                except NotImplementedError:
                    pass
                try:
                    peltier.stop()
                except Exception:
                    pass
                try:
                    led.blink(LedState.RED, on_time=0.3, off_time=0.3)
                except NotImplementedError:
                    pass

                if mqtt_client is not None:
                    try:
                        mqtt_client.publish_actuator_state(
                            "failsafe",
                            {"status": "FAILSAFE_ACTIVE", "reason": "SENSOR_ERROR"},
                        )
                    except Exception:
                        pass
                if influx_writer is not None:
                    try:
                        influx_writer.write_point(
                            "alerts",
                            {"failsafe_active": 1.0},
                            tags={"type": "sensor_error"},
                        )
                    except Exception:
                        pass
                time.sleep(loop_interval_s)
                continue

            # 2b. Protecție termică dedicată Peltier (TEC1-12706 max 60°C)
            peltier_safe, safety_msg = check_peltier_thermal_safety(hot_temp)
            if not peltier_safe:
                logger.critical("%s Decuplare forțată Peltier!", safety_msg)
                try:
                    peltier.stop()
                except Exception:
                    pass
                if mqtt_client is not None:
                    try:
                        mqtt_client.publish_actuator_state(
                            "failsafe",
                            {"status": "PELTIER_TRIPPED", "reason": "THERMAL_CUTOFF", "message": safety_msg},
                        )
                    except Exception:
                        pass
                if influx_writer is not None:
                    try:
                        influx_writer.write_point(
                            "alerts",
                            {"peltier_cutoff": 1.0, "hot_temp_c": hot_temp if hot_temp is not None else -999.0},
                            tags={"type": "peltier_thermal"},
                        )
                    except Exception:
                        pass

            # 3. Calcul variabile de mediu
            calc_flow = PIPE_FLOW_REAL_BUILDING_L_S if getattr(pump, "is_on", False) else 0.05
            calc_head = PIPE_HEAD_REAL_BUILDING_M if getattr(pump, "is_on", False) else 2.0
            calc_pper_w = pper_power_w(flow_rate_l_s=calc_flow, head_m=calc_head)
            price_signal = hourly_energy_price(hour_of_day)
            hvac_w = hvac_load_w(hour_of_day=hour_of_day)

            # 4. Reconstruire obiect Observation conform interfaces.py (fix 6 valori)
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
            except Exception as err:
                logger.error("Eroare în inferența RL: %s. Se aplică decizia de siguranță.", err)
                action = Action(pump_on=False, pump_speed_pct=0.0)

            # 6. Comandă actuatoare (Pompă & LED)
            try:
                pump.apply(action)
            except NotImplementedError:
                logger.debug("Comandă pompă fallback: pump_on=%s, speed=%.1f%%", action.pump_on, action.pump_speed_pct)

            try:
                if action.pump_on:
                    led.set_state(LedState.GREEN)
                else:
                    led.set_state(LedState.BLUE)
            except NotImplementedError:
                pass

            # 7. Publicare mesaje MQTT conform interfaces.py
            if mqtt_client is not None:
                try:
                    mqtt_client.publish_sensor_reading("temp1", utl_temp, "C")
                    mqtt_client.publish_sensor_reading("temp_reservoir", utl_temp, "C")
                    if cold_temp is not None:
                        mqtt_client.publish_sensor_reading("temp_peltier_cold", cold_temp, "C")
                    if hot_temp is not None:
                        mqtt_client.publish_sensor_reading("temp_peltier_hot", hot_temp, "C")
                    mqtt_client.publish_sensor_reading("pressure", pper_pressure, "bar")

                    if hasattr(pump, "to_telemetry_message"):
                        mqtt_client.publish_actuator_state("pump", pump.to_telemetry_message())
                    if hasattr(peltier, "to_telemetry_message"):
                        mqtt_client.publish_actuator_state("peltier", peltier.to_telemetry_message())
                    if hasattr(led, "to_telemetry_message"):
                        mqtt_client.publish_actuator_state("led", led.to_telemetry_message())
                except Exception:
                    pass

            # 8. Scriere serii temporale în InfluxDB
            if influx_writer is not None:
                try:
                    point_data = {
                        "utl_temperature_c": utl_temp,
                        "pper_pressure_bar": pper_pressure,
                        "pper_power_w": calc_pper_w,
                        "hvac_load_w": hvac_w,
                        "energy_price": price_signal,
                    }
                    if cold_temp is not None:
                        point_data["cold_side_temp_c"] = cold_temp
                    if hot_temp is not None:
                        point_data["hot_side_temp_c"] = hot_temp

                    influx_writer.write_point(
                        "sensor_readings",
                        point_data,
                        tags={"device": "raspberry_pi_4"},
                    )
                    influx_writer.write_point(
                        "actuator_states",
                        {
                            "pump_on": 1.0 if action.pump_on else 0.0,
                            "pump_speed_pct": float(action.pump_speed_pct),
                            "peltier_on": 1.0 if peltier.is_on else 0.0,
                        },
                        tags={"device": "hardware_drivers"},
                    )
                except Exception:
                    pass

            logger.info(
                "[Pas %d] REZERVOR=%.2f°C | PELTIER RECE=%s | PELTIER CALD=%s | P_PPER=%.3f bar (%.2f W) | Tarif=%.2f | Pompă=%s (%.0f%%)",
                step_count,
                utl_temp,
                f"{cold_temp:.2f}°C" if cold_temp is not None else "N/A",
                f"{hot_temp:.2f}°C" if hot_temp is not None else "N/A",
                pper_pressure,
                calc_pper_w,
                price_signal,
                "ON" if action.pump_on else "OFF",
                action.pump_speed_pct,
            )

            if max_loops is not None and step_count >= max_loops:
                logger.info("S-a atins numărul maxim de bucle (%d). Oprire.", max_loops)
                break

            time.sleep(loop_interval_s)

    except KeyboardInterrupt:
        logger.info("Oprire cerută de utilizator (Ctrl+C). Dezactivare actuatoare...")
    finally:
        try:
            if hasattr(pump, "stop"):
                pump.stop()
            else:
                pump.apply(Action(pump_on=False, pump_speed_pct=0.0))
        except Exception:
            pass

        try:
            peltier.stop()
        except Exception:
            pass

        try:
            led.off()
        except Exception:
            pass

        if mqtt_client is not None:
            try:
                mqtt_client.disconnect()
            except Exception:
                pass

        if influx_writer is not None:
            try:
                influx_writer.close()
            except Exception:
                pass

        logger.info("Resurse eliberate. Sistem Oprit.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Buclă principală control RPi (MVP 4).")
    parser.add_argument("--model-path", type=str, default=ONNX_MODEL_PATH, help="Calea către fișierul model ONNX")
    parser.add_argument("--interval", type=float, default=1.0, help="Interval între citiri/decizii (secunde)")
    parser.add_argument("--simulated", action="store_true", help="Rulează în mod simulat fără acces hardware 1-Wire/I2C")
    parser.add_argument("--max-loops", type=int, default=None, help="Număr maxim de iterații (util pentru teste/CI)")
    args = parser.parse_args()

    run_control_loop(
        model_path=args.model_path,
        loop_interval_s=args.interval,
        simulated=args.simulated,
        max_loops=args.max_loops,
    )


if __name__ == "__main__":
    main()
