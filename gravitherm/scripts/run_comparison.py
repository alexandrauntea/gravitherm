"""Rulează un scenariu comparativ baseline (ON/OFF) vs. agent RL și afișează tabelul de metrici.

Rulare: python scripts/run_comparison.py [--duration 1440]
"""

import argparse
from pathlib import Path
from stable_baselines3 import PPO

from gravitherm.agent.env_adapter import obs_to_array
from gravitherm.config import COMFORT_TEMP_MAX_C, COMFORT_TEMP_MIN_C
from gravitherm.simulation.env import GraviThermEnv
from scripts.baseline_onoff import run_baseline_episode


def evaluate_ppo_episode(
    env: GraviThermEnv, model: PPO, num_steps: int = 1440
) -> list[dict]:
    obs_raw, _ = env.reset(seed=42)
    records = []

    for step_idx in range(num_steps):
        obs_arr = obs_to_array(obs_raw)
        action, _ = model.predict(obs_arr, deterministic=True)
        action = int(action)

        record = {
            "step": step_idx,
            "hour_of_day": obs_raw["hour_of_day"],
            "utl_temperature_c": obs_raw["utl_temperature_c"],
            "pper_pressure_bar": obs_raw["pper_pressure_bar"],
            "pper_power_w": obs_raw["pper_power_w"],
            "energy_price": obs_raw["energy_price"],
            "hvac_load_w": obs_raw["hvac_load_w"],
            "action": action,
        }
        records.append(record)

        obs_raw, _, terminated, truncated, _ = env.step(action)
        if terminated or truncated:
            break

    return records


def compute_metrics(records: list[dict]) -> dict:
    total_pper_wh = sum(r["pper_power_w"] for r in records) / 60.0
    avg_temp = sum(r["utl_temperature_c"] for r in records) / len(records)
    pump_on_pct = (sum(1 for r in records if r["action"] == 1) / len(records)) * 100.0

    comfort_count = sum(
        1
        for r in records
        if COMFORT_TEMP_MIN_C <= r["utl_temperature_c"] <= COMFORT_TEMP_MAX_C
    )
    comfort_pct = (comfort_count / len(records)) * 100.0

    grid_cost = sum(
        max(0.0, r["hvac_load_w"] - r["pper_power_w"])
        * r["energy_price"]
        * (1.0 / 60.0)
        for r in records
    )

    return {
        "total_pper_wh": round(total_pper_wh, 2),
        "avg_temp": round(avg_temp, 2),
        "pump_on_pct": round(pump_on_pct, 1),
        "comfort_pct": round(comfort_pct, 1),
        "grid_cost": round(grid_cost, 2),
    }


def main():
    parser = argparse.ArgumentParser(description="Compară baseline ON/OFF vs. agent RL.")
    parser.add_argument(
        "--duration", type=int, default=1440, help="Durata sesiunii în minute/pași (default: 1440 = 24h)"
    )
    args = parser.parse_args()

    env = GraviThermEnv()
    baseline_records = run_baseline_episode(env=env, num_steps=args.duration)
    baseline_metrics = compute_metrics(baseline_records)

    model_path = Path("models/ppo_gravitherm.zip")
    if not model_path.exists():
        model_path = Path("models/ppo_gravitherm")

    if not model_path.exists():
        print(f"Model ONNX/SB3 negăsit la {model_path}, se antrenează rapid PPO...")
        from gravitherm.agent.train_ppo import main as train_main

        train_main(total_timesteps=2048, save_path="models/ppo_gravitherm")

    model = PPO.load(model_path)
    env_rl = GraviThermEnv()
    rl_records = evaluate_ppo_episode(env=env_rl, model=model, num_steps=args.duration)
    rl_metrics = compute_metrics(rl_records)

    header = "=" * 66
    print()
    print(header)
    print("      GRAVITHERM - REZULTATE COMPARAȚIE FAZA I (MVP 2)")
    print(header)
    print(f"{'Metrica':<32} | {'Baseline ON/OFF':<14} | {'Agent RL (PPO)':<14}")
    print("-" * 66)
    print(
        f"{'Energie PPER generată (Wh)':<32} | {baseline_metrics['total_pper_wh']:<14} | {rl_metrics['total_pper_wh']:<14}"
    )
    print(
        f"{'Temperatura medie UTL (°C)':<32} | {baseline_metrics['avg_temp']:<14} | {rl_metrics['avg_temp']:<14}"
    )
    print(
        f"{'Conformitate confort (21-24°C) %':<32} | {baseline_metrics['comfort_pct']:<14} | {rl_metrics['comfort_pct']:<14}"
    )
    print(
        f"{'Timp funcționare pompă (%)':<32} | {baseline_metrics['pump_on_pct']:<14} | {rl_metrics['pump_on_pct']:<14}"
    )
    print(
        f"{'Cost energie rețea (norm)':<32} | {baseline_metrics['grid_cost']:<14} | {rl_metrics['grid_cost']:<14}"
    )
    print(header)
    print()


if __name__ == "__main__":
    main()
