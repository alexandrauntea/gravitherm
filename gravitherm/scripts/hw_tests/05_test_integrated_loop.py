#!/usr/bin/env python3
"""Pasul 5 — Buclă Integrată de Test (Hardware Real + BMP280 Mock + Agent RL / Baseline).

Rulează un ciclu complet de orchestrat IoT pe Raspberry Pi timp de 2.5 minute (150s):
- Actuatoare reale: Pompă L298N (GPIO23, GPIO24) și Modul Peltier (GPIO25).
- Senzori reali: DS18B20 pe 1-Wire (monitorizează toți senzorii conectați).
- Senzor mock: BMP280 returnează mock (1.013 bar, 22.5°C) fără erori.
- Indicator LED: Mock / dezactivat fără acces GPIO.
- Agent de decizie: Încarcă ONNX dacă există în models/, altfel folosește controllerul
  baseline ON/OFF cu histerezis termic și conștientizare tarifară.
- Servicii de telemetrie: MQTT și InfluxDB se conectează doar dacă Docker rulează;
  dacă nu sunt active, se continuă în mod offline cu mesaj informativ.
- Siguranță absolută: Limită termică 50°C + try/finally ce oprește toate actuatoarele.
"""

from __future__ import annotations

import glob
import re
import socket
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SRC_PATH = REPO_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

import gravitherm.config as cfg
from gravitherm.interfaces import Action, Observation
from gravitherm.iot.actuators.peltier import PeltierController
from gravitherm.iot.actuators.pump import PumpController
from gravitherm.simulation.env import hourly_energy_price
from gravitherm.simulation.hvac_profile import hvac_load_w
from gravitherm.simulation.pper_model import pper_power_w

# Coduri culori ANSI
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_RED = "\033[91m"
COLOR_CYAN = "\033[96m"
COLOR_MAGENTA = "\033[95m"
COLOR_BOLD = "\033[1m"
COLOR_RESET = "\033[0m"

TOTAL_DURATION_S = 150.0  # 2.5 minute conform cerinței (2-3 minute)
LOOP_INTERVAL_S = 2.0     # pas de 2 secunde


def read_sysfs_temperature(sensor_path: str) -> float | None:
    slave_file = Path(sensor_path) / "w1_slave"
    if not slave_file.exists():
        return None
    try:
        with open(slave_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
        if len(lines) >= 2 and "YES" in lines[0]:
            match = re.search(r"t=(-?\d+)", lines[1])
            if match:
                return int(match.group(1)) / 1000.0
    except Exception:
        pass
    return None


def is_service_port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except (OSError, TimeoutError):
        return False


def load_agent_policy():
    onnx_path = REPO_ROOT / cfg.ONNX_MODEL_PATH
    if onnx_path.exists():
        try:
            from gravitherm.agent.inference import PolicyRunner
            policy = PolicyRunner(str(onnx_path))
            print(f"  {COLOR_GREEN}[AGENT] Model ONNX găsit și încărcat: {onnx_path}{COLOR_RESET}")
            return policy, "ONNX_RL"
        except Exception as err:
            print(f"  {COLOR_YELLOW}[AGENT] Eroare încărcare ONNX ({err}). Se trece pe Baseline.{COLOR_RESET}")

    # Fallback pe Baseline Controller
    from gravitherm.iot.rpi_main import EnergyAwarePolicyStub
    print(f"  {COLOR_CYAN}[AGENT] Se folosește EnergyAwarePolicyStub (Histerezis termic & tarif orar){COLOR_RESET}")
    return EnergyAwarePolicyStub(), "BASELINE_STUB"


def main() -> int:
    print("=" * 85)
    print(f"{COLOR_BOLD}{COLOR_CYAN}GRAVITHERM — PAS 5: BUCLĂ INTEGRATĂ DE CONTROL ȘI MONITORIZARE{COLOR_RESET}")
    print("=" * 85)
    print(f"Durată test: {TOTAL_DURATION_S:.0f}s (2.5 min) | Pas: {LOOP_INTERVAL_S:.1f}s | Limitare termică: 50.0°C\n")

    # 1. Verificare telemetrie (Docker / MQTT / InfluxDB)
    print(f"{COLOR_BOLD}1. Verificare servicii telemetrie:{COLOR_RESET}")
    mqtt_online = is_service_port_open(cfg.MQTT_BROKER_HOST, cfg.MQTT_BROKER_PORT)
    influx_online = is_service_port_open("localhost", 8086)

    mqtt_client = None
    influx_writer = None

    if mqtt_online:
        print(f"  {COLOR_GREEN}[OK] Broker MQTT activ pe {cfg.MQTT_BROKER_HOST}:{cfg.MQTT_BROKER_PORT}{COLOR_RESET}")
        try:
            from gravitherm.iot.mqtt_client import GraviThermMQTTClient
            mqtt_client = GraviThermMQTTClient()
            mqtt_client.connect()
        except Exception as err:
            print(f"  {COLOR_YELLOW}[WARN] Conexiune MQTT eșuată: {err}{COLOR_RESET}")
    else:
        print(f"  {COLOR_YELLOW}[INFO] Docker MQTT broker nu rulează -> continuăm în mod offline fără MQTT.{COLOR_RESET}")

    if influx_online:
        print(f"  {COLOR_GREEN}[OK] InfluxDB activ pe localhost:8086{COLOR_RESET}")
        try:
            from gravitherm.iot.influx_writer import InfluxDBWriter
            influx_writer = InfluxDBWriter()
        except Exception as err:
            print(f"  {COLOR_YELLOW}[WARN] Conexiune InfluxDB eșuată: {err}{COLOR_RESET}")
    else:
        print(f"  {COLOR_YELLOW}[INFO] InfluxDB nu rulează -> continuăm fără persistență serii temporale.{COLOR_RESET}")

    # 2. Descoperire senzori DS18B20
    print(f"\n{COLOR_BOLD}2. Descoperire senzori 1-Wire:{COLOR_RESET}")
    sensor_paths = sorted(glob.glob("/sys/bus/w1/devices/28-*"))
    is_mock_sensors = False
    if not sensor_paths:
        print(f"  {COLOR_YELLOW}[WARN] Nu s-au detectat senzori DS18B20 fizici pe magistrală.{COLOR_RESET}")
        resp = input("  Doriți să rulați în mod hibrid cu senzori de temperatură simulați? (y/N): ").strip().lower()
        if resp != "y":
            print("Test anulat.")
            return 1
        is_mock_sensors = True
        sensor_paths = ["mock_28-001_utl", "mock_28-002_radiator", "mock_28-003_ambient"]

    print(f"  {COLOR_GREEN}[OK] {len(sensor_paths)} senzor(i) disponibili în buclă:{COLOR_RESET}")
    for p in sensor_paths:
        print(f"       • {Path(p).name}")

    # 3. Încărcare agent
    print(f"\n{COLOR_BOLD}3. Încărcare politică de control:{COLOR_RESET}")
    policy, policy_type = load_agent_policy()

    # 4. Confirmare pornire de la utilizator
    print("\n" + f"{COLOR_YELLOW}" + "-" * 85)
    print("  [CONFIRMARE DE SIGURANȚĂ]")
    print("  Pompa trebuie să fie în apă, iar ventilatorul Peltier alimentat.")
    print("  Pompa și modulul Peltier vor fi comandate sincron conform deciziilor agentului.")
    print("-" * 85 + f"{COLOR_RESET}\n")

    try:
        input(f"{COLOR_BOLD}Apăsați [ENTER] pentru a porni bucla integrată (sau Ctrl+C pt anulare): {COLOR_RESET}")
    except KeyboardInterrupt:
        print("\nTest anulat.")
        return 0

    # 5. Inițializare actuatoare
    pump = None
    peltier = None
    step_count = 0
    start_time = time.time()
    cutoff_reason = "Durată completă finalizată cu succes (150 secunde)"

    try:
        pump = PumpController(pin_in1=cfg.GPIO_PUMP_IN1, pin_in2=cfg.GPIO_PUMP_IN2, pin_pwm=cfg.GPIO_PUMP_ENA)
        peltier = PeltierController(pin=cfg.GPIO_PELTIER, active_high=True)

        print("\n" + "=" * 85)
        print(f"{'Pas':<4} | {'Timp':<5} | {'T_UTL':<7} | {'Pres':<6} | {'P_PPER':<7} | {'Tarif':<5} | {'Acțiune Agent':<16} | {'Stare Actuatoare'}")
        print("=" * 85)

        while True:
            elapsed = time.time() - start_time
            if elapsed >= TOTAL_DURATION_S:
                break

            step_count += 1
            now = datetime.now()
            hour_of_day = float(now.hour + now.minute / 60.0 + now.second / 3600.0)

            # A. Citire senzori reali DS18B20
            all_readings: dict[str, float] = {}
            overheat_detected = False
            overheat_val = 0.0

            for p in sensor_paths:
                s_name = Path(p).name
                if is_mock_sensors:
                    t = 22.5 + 1.2 * (step_count % 5 == 0)
                else:
                    t = read_sysfs_temperature(p)

                if t is not None:
                    all_readings[s_name] = t
                    if t >= 50.0:
                        overheat_detected = True
                        overheat_val = t
                else:
                    all_readings[s_name] = 22.0

            # Desemnare T_UTL: primul senzor sau senzorul UTL
            primary_sensor_name = Path(sensor_paths[0]).name
            utl_temp = all_readings.get(primary_sensor_name, 22.0)

            # B. Senzor BMP280 Mock (conform specificației hardware)
            pper_pressure = 1.013  # bar (mock atmosferic normal)

            # C. Protecție Fail-Safe
            if overheat_detected:
                cutoff_reason = f"ALERTĂ FAIL-SAFE: Temperatură critică {overheat_val:.1f}°C depășită!"
                print(f"\n{COLOR_RED}{COLOR_BOLD}[OPRIRE CRITICĂ] {cutoff_reason}{COLOR_RESET}")
                break

            # D. Calcul mărimi de mediu simulate conform fizicii GraviTherm
            calc_flow = cfg.PIPE_FLOW_REAL_BUILDING_L_S if pump.is_on else 0.0
            calc_head = cfg.PIPE_HEAD_REAL_BUILDING_M if pump.is_on else 0.0
            power_w = pper_power_w(flow_rate_l_s=calc_flow, head_m=calc_head)
            price = hourly_energy_price(hour_of_day)
            hvac_w = hvac_load_w(hour_of_day=hour_of_day)

            # E. Construire observație conform interfaces.py
            obs = Observation(
                utl_temperature_c=utl_temp,
                pper_pressure_bar=pper_pressure,
                pper_power_w=power_w,
                hour_of_day=hour_of_day,
                energy_price=price,
                hvac_load_w=hvac_w,
            )

            # F. Decizie Agent RL / Baseline
            action = policy.act(obs)

            # G. Comandă Actuatoare fizice
            pump.apply(action)
            # Peltier-ul este sincronizat cu ciclul de răcire al pompei
            peltier.apply(action.pump_on)

            # H. Publicare Telemetrie dacă serviciile sunt pornite
            if mqtt_client and mqtt_client.is_connected:
                mqtt_client.publish_sensor_reading("temp_utl", utl_temp, "C")
                mqtt_client.publish_actuator_state("pump", pump.to_telemetry_message())
                mqtt_client.publish_actuator_state("peltier", peltier.to_telemetry_message())

            if influx_writer and influx_writer.is_connected:
                influx_writer.write_point(
                    "hw_test_loop",
                    {
                        "utl_temp": utl_temp,
                        "pump_on": 1.0 if pump.is_on else 0.0,
                        "peltier_on": 1.0 if peltier.is_on else 0.0,
                        "pper_power_w": power_w,
                    },
                )

            # I. Afișare stare pas în consolă
            pump_str = f"{COLOR_GREEN}ON{COLOR_RESET}" if pump.is_on else f"{COLOR_YELLOW}OFF{COLOR_RESET}"
            peltier_str = f"{COLOR_GREEN}ON{COLOR_RESET}" if peltier.is_on else f"{COLOR_YELLOW}OFF{COLOR_RESET}"
            act_str = f"Pompă={pump_str} | Pelt={peltier_str}"
            dec_str = f"PUMP={'ON ' if action.pump_on else 'OFF'} ({action.pump_speed_pct:.0f}%)"

            print(
                f"{step_count:^4} | {elapsed:4.0f}s | {utl_temp:5.2f}°C | {pper_pressure:4.2f}b | {power_w:5.2f}W | {price:4.2f} | {dec_str:<16} | {act_str}"
            )

            time.sleep(LOOP_INTERVAL_S)

    except KeyboardInterrupt:
        cutoff_reason = "Oprire solicitată de utilizator (Ctrl+C)"
        print(f"\n{COLOR_YELLOW}[INTERRUPT] {cutoff_reason}{COLOR_RESET}")
    except Exception as err:
        cutoff_reason = f"Excepție în timpul buclei: {err}"
        print(f"\n{COLOR_RED}[EROARE] {cutoff_reason}{COLOR_RESET}")
    finally:
        # SIGURANȚĂ OBLIGATORIE: Oprește garantat toate actuatoarele
        print("\n" + "=" * 85)
        print(f"{COLOR_BOLD}[SIGURANȚĂ FINALLY] Oprire imediată actuatoare fizice...{COLOR_RESET}")
        if pump is not None:
            pump.stop()
            pump.close()
            print("  • Pompă oprită și pini eliberați.")
        if peltier is not None:
            peltier.stop()
            peltier.close()
            print("  • Peltier oprit și pin eliberat.")
        if mqtt_client is not None:
            mqtt_client.disconnect()
        if influx_writer is not None:
            influx_writer.close()

    total_time = time.time() - start_time
    print("-" * 85)
    print(f"{COLOR_BOLD}SUMAR PAS 5 (Timp total: {total_time:.1f}s, Pași executați: {step_count}):{COLOR_RESET}")
    print(f"Stare: {COLOR_GREEN if step_count > 10 else COLOR_YELLOW}{cutoff_reason}{COLOR_RESET}")
    print("=" * 85 + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())