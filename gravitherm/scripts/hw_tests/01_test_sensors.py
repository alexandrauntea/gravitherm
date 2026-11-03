"""Script HW 01: Testare și scanare senzori DS18B20 și BMP280.

Verifică identificarea celor 3 senzori DS18B20 conform rolurilor din config.py:
  - REZERVOR     (28-0000006e6d0e)
  - PELTIER RECE (28-0000006ca69e)
  - PELTIER CALD (28-0000006ffba8)
"""

import sys
import time
from pathlib import Path

# Adaugam src/ in pythonpath daca este rulat direct
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from gravitherm.config import DS18B20_COLD_SIDE, DS18B20_HOT_SIDE, DS18B20_RESERVOIR, DS18B20_ROLES
from gravitherm.iot.sensors import bmp280, ds18b20


def main():
    print("=" * 65)
    print(" [HW 01] SCANARE ȘI VERIFICARE SENZORI GRAVITHERM")
    print("=" * 65)

    print("\n1. Verificare magistrală 1-Wire (GPIO4)...")
    available_ids = ds18b20.get_available_sensors()
    print(f"Senzori DS18B20 detectați pe magistrală ({len(available_ids)}):")
    for s_id in available_ids:
        print(f"  - {s_id}")

    print("\n2. Citire temperaturi mapate pe roluri:")
    temps = ds18b20.read_mapped_temperatures()

    rez_temp = temps.get("reservoir")
    cold_temp = temps.get("cold_side")
    hot_temp = temps.get("hot_side")

    print(f"  [REZERVOR]     ID: {DS18B20_RESERVOIR} -> {rez_temp:.2f}°C" if rez_temp is not None else f"  [REZERVOR]     ID: {DS18B20_RESERVOIR} -> LIPSĂ / EROARE")
    print(f"  [PELTIER RECE] ID: {DS18B20_COLD_SIDE} -> {cold_temp:.2f}°C" if cold_temp is not None else f"  [PELTIER RECE] ID: {DS18B20_COLD_SIDE} -> LIPSĂ / EROARE")
    print(f"  [PELTIER CALD] ID: {DS18B20_HOT_SIDE} -> {hot_temp:.2f}°C" if hot_temp is not None else f"  [PELTIER CALD] ID: {DS18B20_HOT_SIDE} -> LIPSĂ / EROARE")

    print("\n3. Citire senzor presiune BMP280 (I2C):")
    try:
        pressure_res = bmp280.read_pressure()
        print(f"  [BMP280] Presiune: {pressure_res.pressure_bar:.3f} bar ({pressure_res.pressure_bar * 1000:.1f} hPa)")
    except Exception as exc:
        print(f"  [BMP280] Eroare citire / Mock activ: {exc}")

    print("\n" + "=" * 65)
    all_ok = all(t is not None for t in [rez_temp, cold_temp, hot_temp])
    if all_ok:
        print(" REZULTAT: Toți cei 3 senzori DS18B20 au fost identificați cu succes!")
    else:
        print(" ATENȚIE: Unul sau mai mulți senzori nu au răspuns. Verificați conexiunile 1-Wire.")
    print("=" * 65)


if __name__ == "__main__":
    main()

