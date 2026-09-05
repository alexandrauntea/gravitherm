"""Controller Baseline ON/OFF (cu histerezis termic) pentru simularea GraviTherm.

Ruleaza un episod complet de 24h (1440 de pasi de 1 minut) in GraviThermEnv,
salveaza traiectoria in `scripts/baseline_results.csv` si afiseaza metricile de referinta.
"""

import csv
from pathlib import Path

from gravitherm.config import COMFORT_TEMP_MAX_C, COMFORT_TEMP_MIN_C
from gravitherm.simulation.env import GraviThermEnv


def on_off_controller(
    current_temp_c: float,
    pump_is_on: bool,
    t_high: float = COMFORT_TEMP_MAX_C,
    t_low: float = COMFORT_TEMP_MIN_C,
) -> int:
    """Controller euristic cu histerezis termic.

    - Porneste pompa (1) daca temperatura depaseste t_high (24C).
    - Opreste pompa (0) daca temperatura scade sub t_low (21C).
    - Pastreaza starea curenta in intervalul (21Cl, 24C).
    """
    if current_temp_c >= t_high:
        return 1
    elif current_temp_c <= t_low:
        return 0
    return 1 if pump_is_on else 0


def run_baseline_episode(
    env: GraviThermEnv,
    num_steps: int = 1440,
    t_high: float = COMFORT_TEMP_MAX_C,
    t_low: float = COMFORT_TEMP_MIN_C,
) -> list[dict]:
    """Ruleaza un episod de simulare folosind controllerul ON/OFF cu histerezis."""
    obs_dict, _ = env.reset(seed=42)
    pump_is_on = False
    records = []

    for step_idx in range(num_steps):
        current_temp = obs_dict["utl_temperature_c"]
        action = on_off_controller(
            current_temp_c=current_temp,
            pump_is_on=pump_is_on,
            t_high=t_high,
            t_low=t_low,
        )
        pump_is_on = bool(action == 1)

        record = {
            "step": step_idx,
            "hour_of_day": obs_dict["hour_of_day"],
            "utl_temperature_c": obs_dict["utl_temperature_c"],
            "pper_pressure_bar": obs_dict["pper_pressure_bar"],
            "pper_power_w": obs_dict["pper_power_w"],
            "energy_price": obs_dict["energy_price"],
            "hvac_load_w": obs_dict["hvac_load_w"],
            "action": action,
        }
        records.append(record)

        obs_dict, _, terminated, truncated, _ = env.step(action)
        if terminated or truncated:
            break

    return records


def main():
    env = GraviThermEnv()
    records = run_baseline_episode(env=env, num_steps=1440)

    output_path = Path(__file__).parent / "baseline_results.csv"
    fieldnames = list(records[0].keys())
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)

    total_pper_wh = sum(r["pper_power_w"] for r in records) / 60.0
    avg_temp = sum(r["utl_temperature_c"] for r in records) / len(records)
    pump_on_count = sum(1 for r in records if r["action"] == 1)
    pump_on_pct = (pump_on_count / len(records)) * 100.0
    avg_hvac_w = sum(r["hvac_load_w"] for r in records) / len(records)

    print("=== REZULTATE EPISOD BASELINE ON/OFF (24h) ===")
    print(f"Pasi simulati           : {len(records)}")
    print(f"Energie PPER generata   : {total_pper_wh:.2f} Wh")
    print(f"Temperatura medie UTL`   : {avg_temp:.2f} °C")
    print(f"Timp functionare pompa  : {pump_on_pct:.1f} %")
    print(f"Consum mediu HVAC       : {avg_hvac_w:.1f} W")
    print(f"Fisier salvat in        : {output_path}")


if __name__ == "__main__":
    main()
