"""Script HW 02: Testare pompă de circulație (driver L298N).

Pini GPIO:
  - IN1 = GPIO23
  - IN2 = GPIO24
Asigură decuplarea automată a alimentării în blocul `finally`.
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from gravitherm.interfaces import Action
from gravitherm.iot.actuators.pump import PumpController


def main():
    print("=" * 60)
    print(" [HW 02] TESTARE POMPĂ CIRCULAȚIE (L298N)")
    print("=" * 60)

    pump = PumpController()
    try:
        print("1. Pornire pompă la 100% viteză pentru 3 secunde...")
        pump.apply(Action(pump_on=True, pump_speed_pct=100.0))
        time.sleep(3.0)

        print("2. Oprire pompă pentru 2 secunde...")
        pump.stop()
        time.sleep(2.0)

        print("3. Test scurt impuls pornire (1 secundă)...")
        pump.apply(Action(pump_on=True, pump_speed_pct=100.0))
        time.sleep(1.0)

        print("Test finalizat cu succes.")
    except KeyboardInterrupt:
        print("\nTest întrerupt de utilizator.")
    finally:
        print("Oprire de siguranță pompă (cleanup)...")
        try:
            pump.stop()
        except Exception as exc:
            print(f"Eroare oprire pompă: {exc}")
        print("Pompă decuplată în siguranță.")


if __name__ == "__main__":
    main()

