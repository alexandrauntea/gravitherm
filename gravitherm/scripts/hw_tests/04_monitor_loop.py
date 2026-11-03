"""Script HW 04: Buclă de monitorizare continuă senzori pe bancul hardware.

Afișează senzorii explicit după noul lor rol:
  - REZERVOR: XX.X°C (temperatura apei calde / principala pentru agent)
  - PELTIER RECE: XX.X°C ("solul" UTL)
  - PELTIER CALD: XX.X°C (radiator, STRICT siguranță)

Include protecție activă termică: dacă temperatura caldă depășește 60°C sau senzorul
se deconectează, decuplează Peltier-ul și emite o alertă [SAFETY].
"""

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from gravitherm.config import HOT_SIDE_LIMIT_C, HOT_SIDE_WARN_C
from gravitherm.iot.actuators.peltier import PeltierController
from gravitherm.iot.actuators.pump import PumpController
from gravitherm.iot.sensors import bmp280, ds18b20


def main():
    parser = argparse.ArgumentParser(description="Monitorizare hardware continuă senzori (HW 04).")
    parser.add_argument("--interval", type=float, default=1.0, help="Interval între citiri (secunde)")
    parser.add_argument("--peltier-on", action="store_true", help="Pornește Peltier-ul în timpul monitorizării")
    args = parser.parse_args()

    print("=" * 75)
    print(" [HW 04] MONITORIZARE CONTINUĂ SENZORI ȘI SUPRAVEGHERE FAIL-SAFE")
    print(f" Limită termică radiator Peltier: {HOT_SIDE_LIMIT_C}°C (Avertizare: {HOT_SIDE_WARN_C}°C)")
    print("=" * 75)

    pump = PumpController()
    peltier = PeltierController()

    if args.peltier_on:
        print("Modul Peltier este ACTIVAT pentru test.")
        peltier.turn_on()
    else:
        print("Modul Peltier este OPRIT (doar monitorizare temperatură).")
        peltier.stop()

    step = 0
    try:
        while True:
            step += 1
            temps = ds18b20.read_mapped_temperatures()
            rez_temp = temps.get("reservoir")
            cold_temp = temps.get("cold_side")
            hot_temp = temps.get("hot_side")

            # Formatare afișare
            rez_str = f"{rez_temp:.2f}°C" if rez_temp is not None else "LIPSĂ"
            cold_str = f"{cold_temp:.2f}°C" if cold_temp is not None else "LIPSĂ"
            hot_str = f"{hot_temp:.2f}°C" if hot_temp is not None else "LIPSĂ"

            try:
                press_val = bmp280.read_pressure().pressure_bar
                press_str = f"{press_val:.3f} bar"
            except Exception:
                press_str = "1.013 bar (mock)"

            # Verificare protecție radiator Peltier
            safety_alert = ""
            if hot_temp is None:
                safety_alert = f" [SAFETY] Senzorul cald lipsește! Peltier oprit forțat."
                if peltier.is_on:
                    peltier.stop()
            elif hot_temp >= HOT_SIDE_LIMIT_C:
                safety_alert = f" [SAFETY] RADIATOR CRITIC ({hot_temp:.1f}°C >= {HOT_SIDE_LIMIT_C}°C)! Tăiere alimentare!"
                if peltier.is_on:
                    peltier.stop()
            elif hot_temp >= HOT_SIDE_WARN_C:
                safety_alert = f" [WARNING] Radiator cald: {hot_temp:.1f}°C"

            print(
                f"[{step:04d}] REZERVOR: {rez_str} | PELTIER RECE: {cold_str} | PELTIER CALD: {hot_str} | PRESIUNE: {press_str}{safety_alert}"
            )

            time.sleep(args.interval)

    except KeyboardInterrupt:
        print("\nMonitorizare oprită de utilizator.")
    finally:
        print("Oprire de siguranță toate actuatoarele...")
        try:
            pump.stop()
        except Exception:
            pass
        try:
            peltier.stop()
        except Exception:
            pass
        print("Sistem decuplat în siguranță.")


if __name__ == "__main__":
    main()

