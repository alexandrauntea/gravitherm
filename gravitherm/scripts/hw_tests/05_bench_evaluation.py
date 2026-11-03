"""Script HW 05: Evaluare și comparație pe bancul hardware fizic (RL ONNX vs. Baseline ON/OFF).

Rulează bucla închisă de control pe bancul fizic cu oricare dintre politici:
  - Agentul RL (model ONNX exportat)
  - Controller-ul Baseline ON/OFF (cu histerezis termic)

Afișează clar:
  - Politica activă (ONNX vs Baseline)
  - Calea modelului ONNX încărcat
  - Decizia pas-cu-pas (Pompă ON/OFF, viteză %)
  - Temperaturile mapate pe roluri (REZERVOR, PELTIER RECE, PELTIER CALD)
  - Supravegherea termică de siguranță cu oprire automată a actuatoarelor în finally.
"""

import argparse
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from gravitherm.agent.evaluation import BaselineOnOffPolicy
from gravitherm.config import (
    COMFORT_TEMP_MAX_C,
    COMFORT_TEMP_MIN_C,
    HOT_SIDE_LIMIT_C,
    HOT_SIDE_WARN_C,
    ONNX_MODEL_PATH,
    PIPE_FLOW_REAL_BUILDING_L_S,
    PIPE_HEAD_REAL_BUILDING_M,
)
from gravitherm.interfaces import Action, Observation
from gravitherm.iot.actuators.peltier import PeltierController
from gravitherm.iot.actuators.pump import PumpController
from gravitherm.iot.sensors import bmp280, ds18b20
from gravitherm.simulation.env import hourly_energy_price
from gravitherm.simulation.hvac_profile import hvac_load_w
from gravitherm.simulation.pper_model import pper_power_w


def main():
    parser = argparse.ArgumentParser(description="Evaluare hardware pe banc (HW 05).")
    parser.add_argument("--policy", choices=["onnx", "baseline"], default="onnx", help="Politica de control de evaluat")
    parser.add_argument("--model-path", type=str, default=ONNX_MODEL_PATH, help="Calea către modelul ONNX")
    parser.add_argument("--interval", type=float, default=2.0, help="Interval între pași (secunde)")
    parser.add_argument("--steps", type=int, default=30, help="Număr de pași de rulat (default 30)")
    parser.add_argument("--peltier-on", action="store_true", help="Menține Peltier-ul pornit pe durata testului")
    args = parser.parse_args()

    print("=" * 80)
    print(" [HW 05] EVALUARE ȘI COMPARAȚIE PE BANCUL HARDWARE GRAVITHERM")
    print(f" Politică selectată:   {args.policy.upper()}")
    if args.policy == "onnx":
        abs_model = os.path.abspath(args.model_path)
        print(f" Fișier model ONNX:    {abs_model}")
        print(f" Existență model ONNX: {'GĂSIT' if os.path.exists(abs_model) else 'LIPSĂ (trebuie rulat export_onnx)'}")
    else:
        print(f" Politică clasică:     Baseline ON/OFF cu histerezis [{COMFORT_TEMP_MIN_C}°C, {COMFORT_TEMP_MAX_C}°C]")
    print(f" Protecție radiator:   Tăiere la >= {HOT_SIDE_LIMIT_C}°C | Avertizare la >= {HOT_SIDE_WARN_C}°C")
    print("=" * 80)

    # Inițializare controler / politică
    policy_runner = None
    if args.policy == "onnx":
        try:
            from gravitherm.agent.inference import PolicyRunner

            policy_runner = PolicyRunner(model_path=args.model_path)
            print(">> PolicyRunner ONNX inițializat cu succes.")
        except Exception as exc:
            print(f">> EROARE la inițializarea PolicyRunner ONNX ({exc}).")
            print(">> Se comută automat pe fallback Baseline ON/OFF pentru siguranța bancului.")
            policy_runner = BaselineOnOffPolicy()
    else:
        policy_runner = BaselineOnOffPolicy()
        print(">> Controller Baseline ON/OFF inițializat.")

    pump = PumpController()
    peltier = PeltierController()

    if args.peltier_on:
        print(">> Element Peltier ACTIVAT pentru test.")
        peltier.turn_on()
    else:
        peltier.stop()

    print("\nPornire buclă de evaluare hardware...\n")

    try:
        for step in range(1, args.steps + 1):
            now = datetime.now(UTC)
            hour_of_day = float(now.hour + now.minute / 60.0)

            # 1. Citire temperaturi pe roluri
            temps = ds18b20.read_mapped_temperatures()
            rez_temp = temps.get("reservoir")
            cold_temp = temps.get("cold_side")
            hot_temp = temps.get("hot_side")

            # Rezervorul alimentează temperatura principală UTL a clădirii
            utl_temp = rez_temp if rez_temp is not None else 22.0

            # 2. Citire presiune BMP280
            try:
                pressure_bar = bmp280.read_pressure().pressure_bar
            except Exception:
                pressure_bar = 1.013

            # 3. Protecție termică Peltier
            if hot_temp is None:
                print(f"  [SAFETY] Senzorul cald lipsește! Decuplare imediată Peltier.")
                peltier.stop()
            elif hot_temp >= HOT_SIDE_LIMIT_C:
                print(f"  [SAFETY] Alertă radiator critic: {hot_temp:.1f}°C >= {HOT_SIDE_LIMIT_C}°C! Decuplare imediată!")
                peltier.stop()
            elif hot_temp >= HOT_SIDE_WARN_C:
                print(f"  [WARNING] Radiator încins: {hot_temp:.1f}°C")

            # 4. Construire Observation (exact cele 6 variabile)
            calc_flow = PIPE_FLOW_REAL_BUILDING_L_S if getattr(pump, "is_on", False) else 0.05
            calc_head = PIPE_HEAD_REAL_BUILDING_M if getattr(pump, "is_on", False) else 2.0
            calc_pper_w = pper_power_w(flow_rate_l_s=calc_flow, head_m=calc_head)
            price_signal = hourly_energy_price(hour_of_day)
            hvac_w = hvac_load_w(hour_of_day=hour_of_day)

            obs = Observation(
                utl_temperature_c=utl_temp,
                pper_pressure_bar=pressure_bar,
                pper_power_w=calc_pper_w,
                hour_of_day=hour_of_day,
                energy_price=price_signal,
                hvac_load_w=hvac_w,
            )

            # 5. Decizie politică (ONNX sau Baseline)
            action = policy_runner.act(obs)

            # 6. Aplicare acțiune pe pompa fizică
            try:
                pump.apply(action)
            except NotImplementedError:
                pass

            # 7. Afișare stare completă cu roluri
            rez_fmt = f"{rez_temp:.2f}°C" if rez_temp is not None else "LIPSĂ"
            cold_fmt = f"{cold_temp:.2f}°C" if cold_temp is not None else "LIPSĂ"
            hot_fmt = f"{hot_temp:.2f}°C" if hot_temp is not None else "LIPSĂ"
            act_str = f"POMPĂ={'ON' if action.pump_on else 'OFF'} ({action.pump_speed_pct:.0f}%)"

            print(
                f"[Pas {step:02d}/{args.steps:02d}] "
                f"REZERVOR: {rez_fmt} | PELTIER RECE: {cold_fmt} | PELTIER CALD: {hot_fmt} | "
                f"P_PPER: {calc_pper_w:.1f}W | {act_str}"
            )

            time.sleep(args.interval)

        print("\nEvaluare pe banc finalizată cu succes.")

    except KeyboardInterrupt:
        print("\nEvaluare întreruptă de utilizator.")
    finally:
        print("\nOprire de siguranță toate actuatoarele (cleanup)...")
        try:
            pump.stop()
        except Exception:
            pass
        try:
            peltier.stop()
        except Exception:
            pass
        print("Toate actuatoarele au fost oprite.")


if __name__ == "__main__":
    main()

