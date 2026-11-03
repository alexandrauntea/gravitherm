#!/usr/bin/env python3
"""Pasul 4 — Test Modul Termoelectric Peltier TEC1-12706 cu Monitorizare Termică DS18B20.

Reguli obligatorii de siguranță:
1. Durată maximă de funcționare: 120 secunde.
2. Oprire automată de urgență (Emergency Cutoff): dacă ORICE senzor depășește 50.0°C.
3. Bloc try/finally obligatoriu: oprește modulul Peltier la orice excepție sau Ctrl+C.
4. La final, calculează și afișează variația de temperatură (Delta T = T_final - T_initial)
   pe fiecare senzor DS18B20 pentru a evalua eficiența răcirii/încălzirii.
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

from gravitherm.config import GPIO_PELTIER

# Coduri culori ANSI
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_RED = "\033[91m"
COLOR_CYAN = "\033[96m"
COLOR_BOLD = "\033[1m"
COLOR_RESET = "\033[0m"

MAX_SAFE_TEMP_C = 50.0
MAX_DURATION_S = 120.0
INTERVAL_S = 2.0


def read_sysfs_sensor(sensor_path: str) -> float | None:
    """Citește temperatura dintr-un senzor 1-Wire."""
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


def get_sensor_paths() -> list[str]:
    return sorted(glob.glob("/sys/bus/w1/devices/28-*"))


def main() -> int:
    print("=" * 80)
    print(f"{COLOR_BOLD}{COLOR_CYAN}GRAVITHERM — PAS 4: TEST MODUL TERMOELECTRIC PELTIER TEC1-12706{COLOR_RESET}")
    print("=" * 80)
    print(f"Comandă MOSFET: GPIO{GPIO_PELTIER} (Active HIGH)")
    print(f"Condiții de siguranță: Durată max {MAX_DURATION_S:.0f}s | Limitare termică oprire de urgență la > {MAX_SAFE_TEMP_C:.1f}°C")
    print(f"Interval eșantionare senzori: {INTERVAL_S:.1f}s\n")

    sensor_paths = get_sensor_paths()
    is_mock_sensors = False
    if not sensor_paths:
        print(f"{COLOR_YELLOW}[WARN] Nu s-au detectat senzori DS18B20 fizici pe magistrală.{COLOR_RESET}")
        resp = input("Rulați cu senzori simulați pentru a testa logica de siguranță a Peltier-ului? (y/N): ").strip().lower()
        if resp != "y":
            print("Test anulat.")
            return 1
        is_mock_sensors = True
        sensor_paths = ["mock_28-001_utl", "mock_28-002_radiator_cald", "mock_28-003_ambient"]

    print(f"{COLOR_GREEN}Senzori monitorizați ({len(sensor_paths)}):{COLOR_RESET}")
    for p in sensor_paths:
        print(f"  • {Path(p).name}")

    print("\n" + f"{COLOR_YELLOW}" + "-" * 80)
    print("  [NOTĂ PRIVIND OPERAREA MODULULUI PELTIER]")
    print("  Asigurați-vă că ventilatorul radiatorului este alimentat și pornit.")
    print("  Dacă temperatura radiatorului depășește 50°C, testul se va opri automat instant!")
    print("-" * 80 + f"{COLOR_RESET}\n")

    try:
        input(f"{COLOR_BOLD}Apăsați [ENTER] pentru a porni Peltier-ul și monitorizarea: {COLOR_RESET}")
    except KeyboardInterrupt:
        print("\nTest anulat de utilizator.")
        return 0

    peltier = None
    cutoff_reason = "Finalizare durată completă (120s)"
    initial_temps: dict[str, float] = {}
    last_temps: dict[str, float] = {}
    temp_histories: dict[str, list[float]] = {Path(p).name: [] for p in sensor_paths}

    # Citire temperaturi inițiale T0
    print("\nCitire temperaturi de bază inițiale (T0)...")
    for p in sensor_paths:
        s_name = Path(p).name
        if is_mock_sensors:
            t0 = 23.0
        else:
            t0 = read_sysfs_sensor(p) or 23.0
        initial_temps[s_name] = t0
        last_temps[s_name] = t0
        print(f"  - {s_name}: {t0:6.2f} °C")

    start_time = time.time()
    try:
        from gravitherm.iot.actuators.peltier import PeltierController
        peltier = PeltierController(pin=GPIO_PELTIER, active_high=True)

        print(f"\n{COLOR_GREEN}[START] Activare modul Peltier pe GPIO{GPIO_PELTIER}...{COLOR_RESET}\n")
        peltier.turn_on()

        print("-" * 80)
        sensor_headers = " | ".join(f"{Path(p).name[:14]:<14}" for p in sensor_paths)
        print(f"{'Timp':<6} | {'Peltier':<8} | {sensor_headers}")
        print("-" * 80)

        step = 0
        while True:
            elapsed = time.time() - start_time
            if elapsed >= MAX_DURATION_S:
                cutoff_reason = f"Timeout atins: durată maximă permisă ({MAX_DURATION_S:.0f}s)"
                break

            step += 1
            readings_row = []
            emergency_triggered = False
            overheat_sensor = ""
            overheat_val = 0.0

            for p in sensor_paths:
                s_name = Path(p).name
                if is_mock_sensors:
                    # Răcire ușoară pe primul senzor, încălzire pe al doilea
                    if "utl" in s_name:
                        t = max(15.0, initial_temps[s_name] - (elapsed * 0.06))
                    elif "radiator" in s_name:
                        t = min(48.0, initial_temps[s_name] + (elapsed * 0.15))
                    else:
                        t = initial_temps[s_name]
                else:
                    t = read_sysfs_sensor(p)

                if t is not None:
                    last_temps[s_name] = t
                    temp_histories[s_name].append(t)
                    readings_row.append(f"{t:6.2f} °C")

                    # Verificare protecție termică la 50°C
                    if t >= MAX_SAFE_TEMP_C:
                        emergency_triggered = True
                        overheat_sensor = s_name
                        overheat_val = t
                else:
                    readings_row.append("   N/A   ")

            # Afișare rând curent
            readings_str = " | ".join(f"{r:<14}" for r in readings_row)
            p_status = f"{COLOR_GREEN}ON{COLOR_RESET}" if peltier.is_on else f"{COLOR_RED}OFF{COLOR_RESET}"
            print(f"{elapsed:5.1f}s | {p_status:<17} | {readings_str}")

            if emergency_triggered:
                cutoff_reason = f"PROTECTIE SUPRAÎNCĂLZIRE: Senzorul {overheat_sensor} a atins {overheat_val:.2f}°C (Limită: {MAX_SAFE_TEMP_C:.1f}°C)!"
                print(f"\n{COLOR_RED}{COLOR_BOLD}[ALERTĂ FAIL-SAFE CRITICĂ] {cutoff_reason}{COLOR_RESET}")
                break

            time.sleep(INTERVAL_S)

    except KeyboardInterrupt:
        cutoff_reason = "Oprire forțată manual de utilizator (Ctrl+C)"
        print(f"\n{COLOR_YELLOW}[INTERRUPT] {cutoff_reason}{COLOR_RESET}")
    except Exception as err:
        cutoff_reason = f"Eroare software neașteptată: {err}"
        print(f"\n{COLOR_RED}[EROARE] {cutoff_reason}{COLOR_RESET}")
    finally:
        # SIGURANȚĂ ABSOLUTĂ: Dezactivare imediată a Peltier-ului
        if peltier is not None:
            try:
                peltier.stop()
                peltier.close()
                print(f"\n{COLOR_BOLD}[SIGURANȚĂ] Modulul Peltier a fost OPRIT fizic în blocul finally.{COLOR_RESET}")
            except Exception as close_err:
                print(f"{COLOR_RED}[AVERTISMENT] Eroare la oprirea Peltier: {close_err}{COLOR_RESET}")

    actual_duration = time.time() - start_time

    # RAPORT FINAL ȘI CALCUL DELTA T
    print("\n" + "=" * 80)
    print(f"{COLOR_BOLD}RAPORT TERMIC FINAL PELTIER (Timp total activ: {actual_duration:.1f}s){COLOR_RESET}")
    print(f"Cauză oprire: {COLOR_BOLD}{cutoff_reason}{COLOR_RESET}")
    print("-" * 80)
    print(f"{'ID Senzor':<24} | {'T_Inițial':<10} | {'T_Final':<10} | {'Delta T':<12} | {'Efect Observat'}")
    print("-" * 80)

    for p in sensor_paths:
        s_name = Path(p).name
        t0 = initial_temps.get(s_name, 0.0)
        tf = last_temps.get(s_name, t0)
        delta = tf - t0

        if delta < -0.5:
            efect = f"{COLOR_CYAN}RĂCIRE ACTIVĂ (↓ {abs(delta):.2f}°C){COLOR_RESET}"
        elif delta > 1.0:
            efect = f"{COLOR_RED}DISIPARE CĂLDURĂ (↑ {delta:.2f}°C){COLOR_RESET}"
        else:
            efect = "Stabil / Fără variație semnificativă"

        print(f"{s_name:<24} | {t0:6.2f} °C  | {tf:6.2f} °C  | {delta:+6.2f} °C    | {efect}")

    print("=" * 80 + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())