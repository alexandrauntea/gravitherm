"""Script HW 03: Testare modul termoelectric Peltier TEC1-12706 (MOSFET GPIO25).

Include protecție termică activă pe partea caldă (senzor 28-0000006ffba8):
  - Tăiere forțată dacă Thot >= 60.0°C (sau dacă senzorul se deconectează).
  - Oprire garantată în blocul finally.
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from gravitherm.config import HOT_SIDE_LIMIT_C, HOT_SIDE_WARN_C
from gravitherm.iot.actuators.peltier import PeltierController
from gravitherm.iot.sensors import ds18b20


def main():
    print("=" * 65)
    print(" [HW 03] TESTARE PELTIER TEC1-12706 (MOSFET GPIO25)")
    print(f" Limită termică siguranță radiator: {HOT_SIDE_LIMIT_C}°C (Avertizare: {HOT_SIDE_WARN_C}°C)")
    print("=" * 65)

    peltier = PeltierController()

    try:
        print("\nVerificare stare inițială senzori...")
        temps = ds18b20.read_mapped_temperatures()
        hot_init = temps.get("hot_side")
        cold_init = temps.get("cold_side")

        print(f"  Radiator (partea caldă): {hot_init:.2f}°C" if hot_init is not None else "  Radiator: LIPSĂ/EROARE")
        print(f"  Partea rece (""sol"" UTL):   {cold_init:.2f}°C" if cold_init is not None else "  Partea rece: LIPSĂ/EROARE")

        if hot_init is None:
            print("[SAFETY] EROARE: Senzorul cald nu răspunde! Testul NU pornește Peltier-ul pentru a evita arderea.")
            return

        if hot_init >= HOT_SIDE_LIMIT_C:
            print(f"[SAFETY] Radiatorul este deja la {hot_init:.2f}°C >= {HOT_SIDE_LIMIT_C}°C! Pornire refuzată.")
            return

        print("\nPornire Peltier pentru 5 secunde cu monitorizare activă de siguranță...")
        peltier.turn_on()

        for step in range(5):
            time.sleep(1.0)
            temps = ds18b20.read_mapped_temperatures()
            thot = temps.get("hot_side")
            tcold = temps.get("cold_side")

            print(f"  Secunda {step + 1}: PELTIER CALD = {thot:.2f}°C | PELTIER RECE = {tcold:.2f}°C" if thot is not None and tcold is not None else f"  Secunda {step + 1}: Eroare citire!")

            if thot is None:
                print("[SAFETY] Alertă: Senzor cald deconectat! Decuplare imediată Peltier!")
                peltier.stop()
                break

            if thot >= HOT_SIDE_LIMIT_C:
                print(f"[SAFETY] DEPĂȘIRE LIMITĂ TERMICĂ ({thot:.2f}°C >= {HOT_SIDE_LIMIT_C}°C)! Decuplare forțată!")
                peltier.stop()
                break

            if thot >= HOT_SIDE_WARN_C:
                print(f"[WARNING] Atenție, radiatorul se încălzește rapid: {thot:.2f}°C")

    except KeyboardInterrupt:
        print("\nTest întrerupt de utilizator.")
    finally:
        print("Oprire siguranță Peltier (cleanup)...")
        try:
            peltier.stop()
        except Exception as exc:
            print(f"Eroare oprire Peltier: {exc}")
        print("Peltier DEZACTIVAT.")


if __name__ == "__main__":
    main()

