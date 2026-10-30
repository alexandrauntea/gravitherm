#!/usr/bin/env python3
"""Pasul 2 — Test și Calibrare Senzori de Temperatură 1-Wire DS18B20.

Cerinte:
- Citește toți senzorii la fiecare 2s, timp de 30s (15 citiri per senzor).
- Afișează ID-ul senzorului și temperatura instantanee.
- Semnalează valori anormale / aberante:
  * -127.0°C (eroare de cablaj, lipsă conexiune DQ sau masă deconectată)
  * +85.0°C (valoarea de reset a DS18B20 dacă se citește înainte de conversia completă)
  * Lipsă senzor / CRC eșuat
- Afișează statistici la final: T_min, T_max, T_medie și stabilitatea lecturilor.
"""

from __future__ import annotations

import glob
import re
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SRC_PATH = REPO_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

# Coduri culori
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_RED = "\033[91m"
COLOR_CYAN = "\033[96m"
COLOR_BOLD = "\033[1m"
COLOR_RESET = "\033[0m"


def read_sysfs_sensor(sensor_path: str) -> tuple[float | None, str]:
    """Citește temperatura direct din fișierul /sys/bus/w1/devices/28-*/w1_slave.

    Format w1_slave standard:
    72 01 4b 46 7f ff 0e 10 57 : crc=57 YES
    72 01 4b 46 7f ff 0e 10 57 t=23125
    """
    slave_file = Path(sensor_path) / "w1_slave"
    if not slave_file.exists():
        return None, "Fișierul w1_slave nu există"

    try:
        with open(slave_file, "r", encoding="utf-8") as f:
            lines = f.readlines()

        if len(lines) < 2:
            return None, "Răspuns trunchiat de la kernel"

        # Verificare CRC (prima linie trebuie să aibă 'YES')
        if "YES" not in lines[0]:
            return None, "Eroare CRC (zgomot pe magistrală sau pull-up inadecvat)"

        # Extragere valoare t= (în miimi de grad Celsius)
        match = re.search(r"t=(-?\d+)", lines[1])
        if not match:
            return None, "Valoare t= negăsită în a doua linie"

        temp_mdeg = int(match.group(1))
        temp_c = temp_mdeg / 1000.0
        return temp_c, "OK"

    except Exception as err:
        return None, f"Excepție I/O: {err}"


def get_available_sensors() -> list[str]:
    """Descoperă toți senzorii DS18B20 (28-*) conectați la sistem."""
    paths = sorted(glob.glob("/sys/bus/w1/devices/28-*"))
    return paths


def main(total_duration_s: float = 30.0, interval_s: float = 2.0) -> int:
    print("=" * 75)
    print(f"{COLOR_BOLD}{COLOR_CYAN}GRAVITHERM — PAS 2: TEST SENZORI TEMPERATURĂ DS18B20 (1-WIRE){COLOR_RESET}")
    print("=" * 75)
    print(f"Durată test: {total_duration_s:.0f} secunde | Interval citire: {interval_s:.1f} secunde\n")

    sensor_paths = get_available_sensors()

    is_mock = False
    if not sensor_paths:
        print(f"{COLOR_YELLOW}[ATENȚIE] Nu s-au detectat senzori fizici în /sys/bus/w1/devices/28-*.{COLOR_RESET}")
        print("          Dacă rulați pe Raspberry Pi, verificați:")
        print("          1. dtoverlay=w1-gpio,gpiopin=4 în /boot/firmware/config.txt")
        print("          2. Rezistența pull-up 4.7kΩ între pinul DQ (GPIO4) și 3.3V")
        print("          3. Cablarea senzorilor (VDD=3.3V, DQ=GPIO4, GND=GND)\n")
        resp = input("Doriți să rulați în mod simulare MOCK pentru a valida logica de test? (y/N): ").strip().lower()
        if resp != "y":
            print("Test anulat de utilizator.")
            return 1
        is_mock = True
        sensor_paths = ["mock_28-000001_utl", "mock_28-000002_radiator", "mock_28-000003_ambient"]

    print(f"{COLOR_GREEN}Senzori activi în test ({len(sensor_paths)} detectați):{COLOR_RESET}")
    for p in sensor_paths:
        name = Path(p).name
        print(f"  • ID Hardware: {COLOR_BOLD}{name}{COLOR_RESET}")

    print("\n" + "-" * 75)
    print(f"{'Pas':<5} | {'Timp':<6} | {'ID Senzor':<22} | {'Temperatură':<13} | {'Stare':<20}")
    print("-" * 75)

    num_iterations = int(total_duration_s / interval_s)
    history: dict[str, list[float]] = {Path(p).name: [] for p in sensor_paths}
    anomaly_counts: dict[str, int] = {Path(p).name: 0 for p in sensor_paths}

    start_time = time.time()
    try:
        for step in range(1, num_iterations + 1):
            elapsed = time.time() - start_time

            for p in sensor_paths:
                sensor_id = Path(p).name

                if is_mock:
                    # Date sintetice plauzibile pentru mock
                    import random
                    base_temp = 22.0 if "utl" in sensor_id else (24.0 if "radiator" in sensor_id else 21.0)
                    temp_c = base_temp + random.uniform(-0.15, 0.15)
                    status = "OK (Simulat)"
                else:
                    temp_c, status = read_sysfs_sensor(p)

                # Diagnostic anomalii conform specificației
                status_color = COLOR_GREEN
                if temp_c is None:
                    status_str = f"LIPSĂ DATE ({status})"
                    status_color = COLOR_RED
                    anomaly_counts[sensor_id] += 1
                elif abs(temp_c - (-127.0)) < 0.1:
                    status_str = "ABERANT -127°C (FIR DECONECTAT)"
                    status_color = COLOR_RED
                    anomaly_counts[sensor_id] += 1
                elif abs(temp_c - 85.0) < 0.1 and step == 1:
                    status_str = "RESET 85.0°C (Power-on default)"
                    status_color = COLOR_YELLOW
                    # 85.0C la pasul 1 este acceptabil ca primă conversie, dar notat
                elif abs(temp_c - 85.0) < 0.1:
                    status_str = "ABERANT 85.0°C (Conversie eșuată)"
                    status_color = COLOR_RED
                    anomaly_counts[sensor_id] += 1
                elif temp_c < 0.0 or temp_c > 65.0:
                    status_str = f"ABERANT (În afara limitelor [0-65°C])"
                    status_color = COLOR_RED
                    anomaly_counts[sensor_id] += 1
                else:
                    status_str = "STABIL OK"
                    history[sensor_id].append(temp_c)

                temp_str = f"{temp_c:6.2f} °C" if temp_c is not None else "   N/A   "
                print(f"{step:^5} | {elapsed:5.1f}s | {sensor_id:<22} | {temp_str:<13} | {status_color}{status_str}{COLOR_RESET}")

            time.sleep(interval_s)

    except KeyboardInterrupt:
        print(f"\n{COLOR_YELLOW}Test întrerupt de utilizator (Ctrl+C).{COLOR_RESET}")

    # Raport statistic final
    print("\n" + "=" * 75)
    print(f"{COLOR_BOLD}RAPORT STATISTIC DS18B20 (după {time.time() - start_time:.1f}s):{COLOR_RESET}")
    print("-" * 75)
    print(f"{'ID Senzor':<22} | {'Citiri':<7} | {'T_Min':<9} | {'T_Max':<9} | {'T_Medie':<9} | {'Stare Generală'}")
    print("-" * 75)

    all_passed = True
    for sensor_id, readings in history.items():
        anomalies = anomaly_counts[sensor_id]
        if readings:
            t_min = min(readings)
            t_max = max(readings)
            t_avg = sum(readings) / len(readings)
            delta = t_max - t_min

            if anomalies == 0 and delta < 2.0:
                verdict = f"{COLOR_GREEN}EXCELENT (Delta={delta:.2f}°C){COLOR_RESET}"
            elif anomalies > 0:
                verdict = f"{COLOR_RED}EROARE ({anomalies} lecturi aberante){COLOR_RESET}"
                all_passed = False
            else:
                verdict = f"{COLOR_YELLOW}Zgomot termic (Delta={delta:.2f}°C){COLOR_RESET}"

            print(f"{sensor_id:<22} | {len(readings):<7} | {t_min:6.2f}°C  | {t_max:6.2f}°C  | {t_avg:6.2f}°C  | {verdict}")
        else:
            print(f"{sensor_id:<22} | {0:<7} | {'N/A':<9} | {'N/A':<9} | {'N/A':<9} | {COLOR_RED}FĂRĂ DATE VALIDE{COLOR_RESET}")
            all_passed = False

    print("=" * 75)
    if all_passed and not is_mock:
        print(f"{COLOR_GREEN}{COLOR_BOLD}PAS 2 REUȘIT: Toți senzorii DS18B20 funcționează și livrează temperaturi stabile!{COLOR_RESET}\n")
        return 0
    elif is_mock:
        print(f"{COLOR_YELLOW}PAS 2 FINALIZAT ÎN MOD MOCK (Senzorii fizici nu au fost testați).{COLOR_RESET}\n")
        return 0
    else:
        print(f"{COLOR_RED}{COLOR_BOLD}PAS 2 EȘUAT: Verificați conexiunile fizice 1-Wire ale senzorilor semnalați cu eroare!{COLOR_RESET}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())