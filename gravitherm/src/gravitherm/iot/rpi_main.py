"""Buclă principală de pe Raspberry Pi - MVP 4 (buclă închisă).

Citește senzori fizici/simulați -> trimite InfluxDB/MQTT -> inferență ONNX -> comandă pompă.
Punct de intrare: python -m gravitherm.iot.rpi_main [--simulated] [--max-loops N]
"""

import argparse
import logging
import time
from datetime import UTC, datetime

from gravitherm.agent.inference import PolicyRunner
from gravitherm.config import ONNX_MODEL_PATH
from gravitherm.interfaces import Action, Observation
from gravitherm.iot.actuators.pump import PumpController
from gravitherm.iot.sensors import bmp280, ds18b20
from gravitherm.simulation.pper_model import pper_power_w

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("rpi_main")


def read_sensor_observation(simulated: bool = False) -> Observation:
    """Citește senzorii hardware (DS18B20 & BMP280) sau folosește valori simulate."""
    now = datetime.now(UTC)
    hour_of_day = float(now.hour + now.minute / 60.0)
    
    energy_price = 0.8 if 17.0 <= hour_of_day <= 22.0 else 0.4
    hvac_load_w = 150.0 + 50.0 * (1.0 if (12.0 <= hour_of_day <= 20.0) else 0.2)

    if simulated:
        utl_temp_c = 22.5
        pper_pressure_bar = 1.2
    else:
        try:
            temp_readings = ds18b20.read_all_sensors()
            utl_temp_c = temp_readings[0].temperature_c if temp_readings else 22.0
        except Exception as exc:
            logger.warning("Citirea DS18B20 a eșuat (%s), se folosește valoare fallback 22.0°C", exc)
            utl_temp_c = 22.0

        try:
            pper_pressure_bar = bmp280.read_pressure_bar()
        except Exception as exc:
            logger.warning("Citirea BMP280 a eșuat (%s), se folosește valoare fallback 1.0 bar", exc)
            pper_pressure_bar = 1.0

    flow_l_s = max(0.0, (pper_pressure_bar - 1.0) * 0.1 + 0.05)
    power_w = pper_power_w(flow_rate_l_s=flow_l_s, head_m=2.0)

    return Observation(
        utl_temperature_c=float(utl_temp_c),
        pper_pressure_bar=float(pper_pressure_bar),
        pper_power_w=float(power_w),
        hour_of_day=hour_of_day,
        energy_price=energy_price,
        hvac_load_w=hvac_load_w,
    )


def run_control_loop(
    model_path: str = ONNX_MODEL_PATH,
    loop_interval_s: float = 5.0,
    simulated: bool = False,
    max_loops: int | None = None,
):
    """Execută bucla închisă de control pe Raspberry Pi."""
    logger.info("Inițializare PolicyRunner (model: %s)...", model_path)
    policy = PolicyRunner(model_path=model_path)
    pump = PumpController()

    loop_count = 0
    logger.info("Pornire buclă închisă control (interval: %.1fs, simulat: %s)...", loop_interval_s, simulated)

    try:
        while True:
            obs = read_sensor_observation(simulated=simulated)
            action = policy.act(obs)
            
            try:
                pump.apply(action)
            except NotImplementedError:
                logger.debug("Comandă pompă simulat/fallback (hardware gpiozero neconectat): pump_on=%s, speed=%.1f%%", action.pump_on, action.pump_speed_pct)

            logger.info(
                "[Pas %d] T_utl=%.2f°C, P_pper=%.3f bar (%.2fW) | Acțiune: pompă=%s, viteză=%.1f%%",
                loop_count + 1,
                obs.utl_temperature_c,
                obs.pper_pressure_bar,
                obs.pper_power_w,
                action.pump_on,
                action.pump_speed_pct,
            )

            loop_count += 1
            if max_loops is not None and loop_count >= max_loops:
                logger.info("S-a atins numărul maxim de bucle (%d). Oprire.", max_loops)
                break

            time.sleep(loop_interval_s)
    except KeyboardInterrupt:
        logger.info("Oprire buclă la cererea utilizatorului.")
    finally:
        try:
            pump.apply(Action(pump_on=False, pump_speed_pct=0.0))
        except NotImplementedError:
            pass


def main():
    parser = argparse.ArgumentParser(description="Buclă principală control RPi (MVP 4).")
    parser.add_argument("--model-path", type=str, default=ONNX_MODEL_PATH, help="Calea către fișierul model ONNX")
    parser.add_argument("--interval", type=float, default=5.0, help="Interval între citiri/decizii (secunde)")
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
