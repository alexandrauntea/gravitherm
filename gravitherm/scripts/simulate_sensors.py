"""Simulator de senzori - publica pe MQTT date sintetice, in acelasi format
in care le-ar publica hardware-ul real (DS18B20 x3 + BMP280).

De ce exista acest script: pana ajunge macheta fizica (Faza II), Andreea
(si oricine altcineva) poate rula tot pipeline-ul MQTT -> InfluxDB -> Grafana
cu date false, dar cu formatul CORECT (acelasi topic + acelasi payload JSON
din interfaces.py). Cand vine hardware-ul, singura schimbare e sursa datelor
(sensors/ds18b20.py si sensors/bmp280.py in loc de acest script) - restul
pipeline-ului (mqtt_client.py, influx_writer.py, dashboard-ul Grafana) ramane
neschimbat si deja testat.

Rulare:
    python scripts/simulate_sensors.py                  # ruleaza continuu
    python scripts/simulate_sensors.py --interval 2      # la fiecare 2s
    python scripts/simulate_sensors.py --duration 300    # se opreste dupa 5 min

Necesita un broker MQTT pornit (vezi infra/docker-compose.yml -> serviciul
mosquitto) si pachetul paho-mqtt instalat.
"""

import argparse
import json
import math
import time
from datetime import UTC, datetime

import paho.mqtt.client as mqtt

from gravitherm.config import MQTT_BROKER_HOST, MQTT_BROKER_PORT, MQTT_TOPIC_PREFIX

# Cei 3 senzori DS18B20 - simulam usoare diferente intre ei, ca in realitate
# (nu sunt calibrati perfect identic), plus o variatie sinusoidala lenta ca sa
# semene cu un ciclu zi/noapte comprimat, nu cu zgomot pur aleator.
TEMP_SENSOR_OFFSETS_C = {"temp1": 0.0, "temp2": -0.3, "temp3": 0.4}
BASE_TEMP_C = 22.0
TEMP_AMPLITUDE_C = 3.0
TEMP_CYCLE_S = 120.0  # o "zi" simulata comprimata la 2 minute, utila pt. demo rapid

BASE_PRESSURE_BAR = 3.0
PRESSURE_NOISE_BAR = 0.05


def make_payload(value: float, unit: str) -> str:
    return json.dumps(
        {
            "timestamp": datetime.now(UTC).isoformat(),
            "value": round(value, 3),
            "unit": unit,
        }
    )


def simulated_temperature(sensor_name: str, elapsed_s: float) -> float:
    offset = TEMP_SENSOR_OFFSETS_C[sensor_name]
    cycle = math.sin(2 * math.pi * elapsed_s / TEMP_CYCLE_S)
    return BASE_TEMP_C + offset + TEMP_AMPLITUDE_C * cycle


def simulated_pressure(elapsed_s: float) -> float:
    import random

    return BASE_PRESSURE_BAR + random.uniform(-PRESSURE_NOISE_BAR, PRESSURE_NOISE_BAR)


def main():
    parser = argparse.ArgumentParser(description="Simulator de senzori GraviTherm (fara hardware).")
    parser.add_argument("--interval", type=float, default=5.0, help="Secunde intre publicari (implicit 5)")
    parser.add_argument(
        "--duration",
        type=float,
        default=None,
        help="Durata totala in secunde (implicit: ruleaza pana la Ctrl+C)",
    )
    parser.add_argument("--broker-host", type=str, default=MQTT_BROKER_HOST)
    parser.add_argument("--broker-port", type=int, default=MQTT_BROKER_PORT)
    args = parser.parse_args()

    client = mqtt.Client(client_id="gravitherm-sensor-simulator")
    client.connect(args.broker_host, args.broker_port)
    client.loop_start()

    print(
        f"[simulator] conectat la {args.broker_host}:{args.broker_port}, public la fiecare {args.interval}s (Ctrl+C pentru oprire)"
    )

    start = time.time()
    try:
        while True:
            elapsed = time.time() - start
            if args.duration is not None and elapsed >= args.duration:
                break

            for sensor_name in TEMP_SENSOR_OFFSETS_C:
                temp = simulated_temperature(sensor_name, elapsed)
                topic = f"{MQTT_TOPIC_PREFIX}/sensors/{sensor_name}"
                client.publish(topic, make_payload(temp, "celsius"))

            pressure = simulated_pressure(elapsed)
            client.publish(f"{MQTT_TOPIC_PREFIX}/sensors/pressure", make_payload(pressure, "bar"))

            print(
                f"[simulator] t={elapsed:5.1f}s  temp1={simulated_temperature('temp1', elapsed):.2f}C  pressure={pressure:.3f}bar"
            )
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\n[simulator] oprit manual.")
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()
