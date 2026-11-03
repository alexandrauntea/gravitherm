#!/usr/bin/env python3
"""Pasul 1 — Verificare Mediu Software și Interfețe Hardware (GraviTherm).

Verifică:
- Versiunea Python (recomandat 3.10 / 3.11 pe Raspberry Pi)
- Bibliotecile Python necesare (gpiozero, onnxruntime, w1thermsensor, paho-mqtt, influxdb-client, numpy)
- Magistrala 1-Wire în kernel (/sys/bus/w1/devices)
- Senzorii DS18B20 detectați în sysfs (directoare 28-*)
- Configurația GraviTherm și integritatea structurii de proiect
"""

from __future__ import annotations

import glob
import importlib
import os
import platform
import sys
from pathlib import Path

# Asigură accesul la pachetul gravitherm din src/
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SRC_PATH = REPO_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

# Coduri ANSI pentru output vizual structurat
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_RED = "\033[91m"
COLOR_CYAN = "\033[96m"
COLOR_BOLD = "\033[1m"
COLOR_RESET = "\033[0m"


def print_status(tag: str, message: str, color: str = COLOR_RESET) -> None:
    print(f"  {color}[{tag}]{COLOR_RESET} {message}")


def check_python_version() -> bool:
    print(f"\n{COLOR_BOLD}1. Verificare versiune Python:{COLOR_RESET}")
    v = sys.version_info
    v_str = f"{v.major}.{v.minor}.{v.micro}"
    arch = platform.machine()
    system = platform.system()
    print(f"   Platformă: {system} ({arch}), Python: {v_str}")

    if v.major == 3 and v.minor in (10, 11):
        print_status("OK", f"Python {v_str} este versiunea optimă pentru Raspberry Pi 4.", COLOR_GREEN)
        return True
    elif v.major == 3 and v.minor >= 12:
        print_status("WARN", f"Python {v_str} detectat. Pe RPi 4 recomandăm Python 3.11 pentru stabilitate onnxruntime.", COLOR_YELLOW)
        return True
    else:
        print_status("FAIL", f"Python {v_str} nesuportat. Este necesar Python >= 3.10.", COLOR_RED)
        return False


def check_python_packages() -> dict[str, bool]:
    print(f"\n{COLOR_BOLD}2. Verificare biblioteci Python necesare:{COLOR_RESET}")
    packages = {
        "gpiozero": ("Control pini GPIO pentru pompă, Peltier, relee", True),
        "onnxruntime": ("Motor inferență model RL pe Raspberry Pi", False),
        "w1thermsensor": ("Citire de nivel înalt senzori 1-Wire DS18B20", False),
        "numpy": ("Manipulare tensori de observație și inferență", True),
        "paho.mqtt": ("Client MQTT pentru publicare telemetrie", False),
        "influxdb_client": ("Client InfluxDB pentru serii temporale", False),
    }

    results: dict[str, bool] = {}
    for pkg_name, (desc, is_critical) in packages.items():
        try:
            mod = importlib.import_module(pkg_name)
            ver = getattr(mod, "__version__", "instalat")
            print_status("OK", f"{pkg_name} ({ver}) — {desc}", COLOR_GREEN)
            results[pkg_name] = True
        except ImportError:
            if is_critical:
                print_status("FAIL", f"{pkg_name} lipsește! ({desc}) -> Necesar: pip install {pkg_name}", COLOR_RED)
                results[pkg_name] = False
            else:
                print_status("WARN", f"{pkg_name} nu este instalat ({desc}) -> Va rula pe fallback/mock", COLOR_YELLOW)
                results[pkg_name] = False

    return results


def check_onewire_bus() -> list[str]:
    print(f"\n{COLOR_BOLD}3. Verificare magistrală 1-Wire (DS18B20):{COLOR_RESET}")
    w1_dir = Path("/sys/bus/w1/devices")

    if not w1_dir.exists():
        print_status("FAIL", "Directoriul /sys/bus/w1/devices NU există!", COLOR_RED)
        print("         -> Asigurați-vă că 1-Wire este activat în kernel:")
        print("            1. sudo raspi-config -> Interface Options -> 1-Wire -> Enable")
        print("            2. SAU adăugați 'dtoverlay=w1-gpio,gpiopin=4' în /boot/firmware/config.txt")
        print("            3. Reboot: sudo reboot")
        return []

    print_status("OK", "Interfața de kernel 1-Wire este activă (/sys/bus/w1/devices găsit).", COLOR_GREEN)

    # Caută senzori DS18B20 (prefix familie 28-*)
    sensors = glob.glob("/sys/bus/w1/devices/28-*")
    sensor_ids = [Path(s).name for s in sensors]

    if not sensor_ids:
        print_status("WARN", "Niciun senzor cu ID 28-* nu a fost detectat pe magistrală!", COLOR_YELLOW)
        print("         -> Verificați cablajul:")
        print("            - VDD (3.3V la pin 1 RPi), GND (la GND RPi)")
        print("            - DQ (Semnal la GPIO4 / pin 7 RPi)")
        print("            - Rezistență pull-up de 4.7kΩ montată între VDD (3.3V) și DQ (semnal)!")
    else:
        print_status("OK", f"{len(sensor_ids)} senzor(i) DS18B20 detectați pe magistrală:", COLOR_GREEN)
        for s_id in sensor_ids:
            slave_file = Path(f"/sys/bus/w1/devices/{s_id}/w1_slave")
            readable = slave_file.exists() and os.access(slave_file, os.R_OK)
            stat = "accesibil" if readable else "protejat la citire"
            print(f"      - {COLOR_CYAN}{s_id}{COLOR_RESET} ({stat})")

    return sensor_ids


def check_project_config() -> bool:
    print(f"\n{COLOR_BOLD}4. Verificare configurație GraviTherm:{COLOR_RESET}")
    try:
        import gravitherm.config as cfg
        print_status("OK", "Fișier config.py încărcat cu succes.", COLOR_GREEN)
        print(f"      - HARDWARE_MODE        : {getattr(cfg, 'HARDWARE_MODE', False)}")
        print(f"      - USE_REAL_DS18B20     : {getattr(cfg, 'USE_REAL_DS18B20', False)}")
        print(f"      - USE_REAL_PUMP        : {getattr(cfg, 'USE_REAL_PUMP', False)} (IN1={getattr(cfg, 'GPIO_PUMP_IN1', 23)}, IN2={getattr(cfg, 'GPIO_PUMP_IN2', 24)}, ENA={getattr(cfg, 'GPIO_PUMP_ENA', None)})")
        print(f"      - USE_REAL_PELTIER     : {getattr(cfg, 'USE_REAL_PELTIER', False)} (GPIO={getattr(cfg, 'GPIO_PELTIER', 25)})")
        print(f"      - USE_REAL_BMP280      : {getattr(cfg, 'USE_REAL_BMP280', False)} (MOCK conform specificației)")
        print(f"      - USE_REAL_LED         : {getattr(cfg, 'USE_REAL_LED', False)} (MOCK conform specificației)")
        return True
    except Exception as err:
        print_status("FAIL", f"Eroare la importul gravitherm.config: {err}", COLOR_RED)
        return False


def main() -> int:
    print("=" * 70)
    print(f"{COLOR_BOLD}{COLOR_CYAN}GRAVITHERM — PAS 1: VERIFICARE MEDIU & HARDWARE RPi{COLOR_RESET}")
    print("=" * 70)

    py_ok = check_python_version()
    pkg_results = check_python_packages()
    sensors = check_onewire_bus()
    cfg_ok = check_project_config()

    print("\n" + "=" * 70)
    print(f"{COLOR_BOLD}REZUMAT PAS 1:{COLOR_RESET}")
    all_critical_ok = py_ok and pkg_results.get("gpiozero", False) and cfg_ok

    if all_critical_ok:
        if len(sensors) >= 1:
            print_status("SUCCESS", "Toate cerințele critice și senzorii 1-Wire sunt prezenți! Gata pentru Pasul 2.", COLOR_GREEN)
            return 0
        else:
            print_status("WARN", "Mediul software este pregătit, dar magistrala 1-Wire nu raportează senzori fizici 28-*.", COLOR_YELLOW)
            return 0
    else:
        print_status("ERROR", "Există erori critice în mediu ce trebuie corectate înainte de testele hardware.", COLOR_RED)
        return 1


if __name__ == "__main__":
    sys.exit(main())