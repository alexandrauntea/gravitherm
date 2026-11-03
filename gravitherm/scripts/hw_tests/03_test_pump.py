#!/usr/bin/env python3
"""Pasul 3 — Test Pompă Submersibilă 12V 10W (QR50D) prin Driver L298N.

Secvență de test:
- Afișează avertisment critic de siguranță (pompa trebuie să fie imersată în apă).
- Așteaptă confirmarea manuală a utilizatorului (tasta Enter).
- Execută 3 cicluri consecutive:
  * Pornire pompă: 3 secunde
  * Oprire pompă: pauză 2 secunde
- Siguranță: Bloc try/finally obligatoriu ce garantează oprirea fizică a pompei la orice excepție sau Ctrl+C.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SRC_PATH = REPO_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from gravitherm.config import GPIO_PUMP_ENA, GPIO_PUMP_IN1, GPIO_PUMP_IN2

# Coduri culori
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_RED = "\033[91m"
COLOR_CYAN = "\033[96m"
COLOR_BOLD = "\033[1m"
COLOR_RESET = "\033[0m"


def main() -> int:
    print("=" * 75)
    print(f"{COLOR_BOLD}{COLOR_CYAN}GRAVITHERM — PAS 3: TEST POMPĂ SUBMERSIBILĂ QR50D (L298N){COLOR_RESET}")
    print("=" * 75)
    print(f"Configurație pini GPIO (BCM): IN1={GPIO_PUMP_IN1}, IN2={GPIO_PUMP_IN2}, ENA={GPIO_PUMP_ENA or 'Jumper montat (100% viteză fixă)'}")

    # AVERTISMENT OBLIGATORIU
    print("\n" + f"{COLOR_RED}{COLOR_BOLD}" + "!" * 75)
    print("  [AVERTISMENT CRITIC DE SIGURANȚĂ]")
    print("  POMPA TREBUIE SĂ FIE SCUFUNDATĂ ÎN APĂ ÎNAINTE DE PORNIRE!")
    print("  Funcționarea fără apă (pe uscat) poate distruge axul ceramic și garniturile")
    print("  în doar câteva secunde de funcționare!")
    print("!" * 75 + f"{COLOR_RESET}\n")

    try:
        input(f"{COLOR_BOLD}Confirmați că pompa este în apă și apăsați [ENTER] pentru a începe testul (Ctrl+C pt anulare): {COLOR_RESET}")
    except KeyboardInterrupt:
        print(f"\n{COLOR_YELLOW}Test anulat de utilizator înainte de pornire.{COLOR_RESET}")
        return 0

    pump = None
    try:
        # 1. Încercare inițializare prin driverul dedicat PumpController
        try:
            from gravitherm.iot.actuators.pump import PumpController
            print(f"\n{COLOR_GREEN}[INFO] Se utilizează driverul oficial gravitherm.iot.actuators.PumpController{COLOR_RESET}")
            pump = PumpController(pin_in1=GPIO_PUMP_IN1, pin_in2=GPIO_PUMP_IN2, pin_pwm=GPIO_PUMP_ENA)
        except Exception as init_err:
            print(f"{COLOR_YELLOW}[WARN] Inițializare PumpController eșuată ({init_err}). Se încearcă fallback direct gpiozero...{COLOR_RESET}")
            from gpiozero import Motor
            pump = Motor(forward=GPIO_PUMP_IN1, backward=GPIO_PUMP_IN2)

        # 2. Executare secvență: 3 cicluri de 3s ON / 2s OFF
        total_cycles = 3
        duration_on_s = 3.0
        duration_off_s = 2.0

        print(f"\n{COLOR_BOLD}Pornire secvență de test ({total_cycles} cicluri)...{COLOR_RESET}\n")

        for cycle in range(1, total_cycles + 1):
            print(f"{COLOR_CYAN}--- Ciclul {cycle}/{total_cycles} ---{COLOR_RESET}")

            # Pornire pompă
            print(f"  [>] Pornire pompă (3.0 secunde)...", end="", flush=True)
            if hasattr(pump, "turn_on"):
                pump.turn_on(100.0)
            elif hasattr(pump, "forward"):
                pump.forward()
            print(f" {COLOR_GREEN}POMPĂ ACTIVĂ [ON]{COLOR_RESET}")

            # Temporizare vizuală
            time.sleep(duration_on_s)

            # Oprire pompă
            print(f"  [X] Oprire pompă (pauză {duration_off_s:.1f} secunde)...", end="", flush=True)
            if hasattr(pump, "turn_off"):
                pump.turn_off()
            elif hasattr(pump, "stop"):
                pump.stop()
            print(f" {COLOR_YELLOW}POMPĂ OPRITĂ [OFF]{COLOR_RESET}\n")

            if cycle < total_cycles:
                time.sleep(duration_off_s)

        print("=" * 75)
        print(f"{COLOR_GREEN}{COLOR_BOLD}PAS 3 REUȘIT: Pompa a executat toate cele 3 cicluri fără erori!{COLOR_RESET}")
        return 0

    except KeyboardInterrupt:
        print(f"\n\n{COLOR_RED}[OPRIRE DE URGENȚĂ] Test întrerupt de utilizator prin Ctrl+C!{COLOR_RESET}")
        return 1
    except Exception as err:
        print(f"\n\n{COLOR_RED}[EROARE CRITICĂ] Excepție întâmpinată în timpul testării pompei: {err}{COLOR_RESET}")
        return 1
    finally:
        # Protecție absolută: Oprește pompa în orice scenariu de ieșire
        if pump is not None:
            try:
                if hasattr(pump, "stop"):
                    pump.stop()
                if hasattr(pump, "close"):
                    pump.close()
                print(f"{COLOR_BOLD}[SIGURANȚĂ] Pinul pompei a fost dezactivat complet în blocul finally.{COLOR_RESET}\n")
            except Exception as close_err:
                print(f"{COLOR_RED}[AVERTISMENT] Eroare la eliberarea resurselor pompei: {close_err}{COLOR_RESET}\n")


if __name__ == "__main__":
    sys.exit(main())