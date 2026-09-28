"""Rulează un scenariu comparativ complet între baseline (ON/OFF) și agentul RL (ONNX / PPO)
pentru evaluarea performanței MVP 4.

Rulare: python scripts/run_comparison.py [--duration 1440] [--onnx-path models/rlaea_policy.onnx]
"""

import argparse
from pathlib import Path
from stable_baselines3 import PPO

from gravitherm.agent.env_adapter import array_to_obs, obs_to_array
from gravitherm.agent.inference import PolicyRunner
from gravitherm.config import COMFORT_TEMP_MAX_C, COMFORT_TEMP_MIN_C, ONNX_MODEL_PATH
from gravitherm.simulation.env import GraviThermEnv
from scripts.baseline_onoff import run_baseline_episode


def evaluate_onnx_episode(env: GraviThermEnv, runner: PolicyRunner, num_steps: int = 1440) -> list[dict]:
    """Evaluează un episod folosind agentul RL via ONNX Inference (PolicyRunner)."""
    obs_raw, _ = env.reset(seed=42)
    records = []

    for step_idx in range(num_steps):
        obs = array_to_obs(obs_to_array(obs_raw))
        action_obj = runner.act(obs)
        discrete_action = 1 if action_obj.pump_on else 0

        record = {
            "step": step_idx,
            "hour_of_day": obs.hour_of_day,
            "utl_temperature_c": obs.utl_temperature_c,
            "pper_pressure_bar": obs.pper_pressure_bar,
            "pper_power_w": obs.pper_power_w,
            "energy_price": obs.energy_price,
            "hvac_load_w": obs.hvac_load_w,
            "action": discrete_action,
        }
        records.append(record)

        obs_raw, _, terminated, truncated, _ = env.step(discrete_action)
        if terminated or truncated:
            break

    return records


def evaluate_ppo_episode(env: GraviThermEnv, model: PPO, num_steps: int = 1440) -> list[dict]:
    """Evaluează un episod folosind modelul antrenat SB3 PPO."""
    obs_raw, _ = env.reset(seed=42)
    records = []

    for step_idx in range(num_steps):
        obs_arr = obs_to_array(obs_raw)
        action, _ = model.predict(obs_arr, deterministic=True)
        discrete_action = int(action)

        record = {
            "step": step_idx,
            "hour_of_day": obs_raw["hour_of_day"],
            "utl_temperature_c": obs_raw["utl_temperature_c"],
            "pper_pressure_bar": obs_raw["pper_pressure_bar"],
            "pper_power_w": obs_raw["pper_power_w"],
            "energy_price": obs_raw["energy_price"],
            "hvac_load_w": obs_raw["hvac_load_w"],
            "action": discrete_action,
        }
        records.append(record)

        obs_raw, _, terminated, truncated, _ = env.step(discrete_action)
        if terminated or truncated:
            break

    return records


def compute_metrics(records: list[dict]) -> dict:
    """Calculează metricile de evaluare pentru o serie de înregistrări."""
    total_pper_wh = sum(r["pper_power_w"] for r in records) / 60.0
    avg_temp = sum(r["utl_temperature_c"] for r in records) / len(records)
    pump_on_pct = (sum(1 for r in records if r["action"] == 1) / len(records)) * 100.0

    comfort_count = sum(
        1 for r in records if COMFORT_TEMP_MIN_C <= r["utl_temperature_c"] <= COMFORT_TEMP_MAX_C
    )
    comfort_pct = (comfort_count / len(records)) * 100.0

    grid_cost = sum(
        max(0.0, r["hvac_load_w"] - r["pper_power_w"]) * r["energy_price"] * (1.0 / 60.0)
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
    parser = argparse.ArgumentParser(description="Comparație Baseline ON/OFF vs. Agent RL (MVP 4).")
    parser.add_argument(
        "--duration", type=int, default=1440, help="Durata sesiunii în pași/minute (default: 1440 = 24h)"
    )
    parser.add_argument("--onnx-path", type=str, default=ONNX_MODEL_PATH, help="Calea fișierului ONNX exportat")
    args = parser.parse_args()

    env_baseline = GraviThermEnv()
    baseline_records = run_baseline_episode(env=env_baseline, num_steps=args.duration)
    baseline_metrics = compute_metrics(baseline_records)

    onnx_path = Path(args.onnx_path)
    if not onnx_path.exists():
        print(f"Modelul ONNX nu există la {onnx_path}. Se antrenează și se exportă automat...")
        from gravitherm.agent.export_onnx import main as export_main
        from gravitherm.agent.train_ppo import main as train_main

        train_main(total_timesteps=2048, save_path="models/ppo_gravitherm")
        export_main(model_path="models/ppo_gravitherm", onnx_path=str(onnx_path))

    runner = PolicyRunner(model_path=str(onnx_path))
    env_rl = GraviThermEnv()
    rl_records = evaluate_onnx_episode(env=env_rl, runner=runner, num_steps=args.duration)
    rl_metrics = compute_metrics(rl_records)

    cost_diff_pct = 0.0
    if baseline_metrics["grid_cost"] > 0:
        cost_diff_pct = (
            (baseline_metrics["grid_cost"] - rl_metrics["grid_cost"]) / baseline_metrics["grid_cost"]
        ) * 100.0

    header = "=" * 70
    print()
    print(header)
    print("      GRAVITHERM - REZULTATE COMPARAȚIE MVP 4 (RPi ONNX vs Baseline)")
    print(header)
    print(f"{'Metrică':<34} | {'Baseline ON/OFF':<14} | {'Agent RL (ONNX)':<14}")
    print("-" * 70)
    print(
        f"{'Energie PPER generată (Wh)':<34} | {baseline_metrics['total_pper_wh']:<14} | {rl_metrics['total_pper_wh']:<14}"
    )
    print(
        f"{'Temperatura medie UTL (°C)':<34} | {baseline_metrics['avg_temp']:<14} | {rl_metrics['avg_temp']:<14}"
    )
    print(
        f"{'Conformitate confort (21-24°C) %':<34} | {baseline_metrics['comfort_pct']:<14} | {rl_metrics['comfort_pct']:<14}"
    )
    print(
        f"{'Timp funcționare pompă (%)':<34} | {baseline_metrics['pump_on_pct']:<14} | {rl_metrics['pump_on_pct']:<14}"
    )
    print(
        f"{'Cost energie rețea (norm)':<34} | {baseline_metrics['grid_cost']:<14} | {rl_metrics['grid_cost']:<14}"
    )
    print("-" * 70)
    print(f"Reducere cost rețea cu agentul RL ONNX: {cost_diff_pct:.1f}%")
    print(header)
    print()


if __name__ == "__main__":
    main()
