"""Rulează un scenariu comparativ baseline (ON/OFF) vs. agent RL și afișează tabelul de metrici.

Rulare: python scripts/run_comparison.py [--duration 1440]
"""

import argparse
import os

from gravitherm.agent.env_adapter import GraviThermAgentEnv
from gravitherm.agent.evaluation import BaselineOnOffPolicy, evaluate_policy
from gravitherm.agent.inference import PolicyRunner


def run_baseline(duration_steps: int) -> dict:
    env = GraviThermAgentEnv()
    baseline_policy = BaselineOnOffPolicy()
    metrics = evaluate_policy(env, baseline_policy, n_steps=duration_steps)
    return metrics.to_dict()


def run_rl_agent(duration_steps: int, model_path: str = "models/rlaea_policy.onnx") -> dict:
    env = GraviThermAgentEnv()
    if not os.path.exists(model_path):
        print(f"Model ONNX negăsit la {model_path}, se generează un model de antrenament rapid...")
        from gravitherm.agent.export_onnx import main as export_main
        from gravitherm.agent.train_ppo import main as train_main

        train_main(total_timesteps=2048, save_path="models/ppo_gravitherm")
        export_main(model_path="models/ppo_gravitherm", onnx_path=model_path)

    runner = PolicyRunner(model_path=model_path)
    metrics = evaluate_policy(env, runner, n_steps=duration_steps)
    return metrics.to_dict()


def main():
    parser = argparse.ArgumentParser(description="Compară baseline ON/OFF vs. agent RL.")
    parser.add_argument(
        "--duration", type=int, default=1440, help="Durata sesiunii în minute/pași (default: 1440 = 24h)"
    )
    parser.add_argument(
        "--onnx-path", type=str, default="models/rlaea_policy.onnx", help="Calea modelului ONNX"
    )
    args = parser.parse_args()

    baseline_metrics = run_baseline(args.duration)
    rl_metrics = run_rl_agent(args.duration, model_path=args.onnx_path)

    header_line = "=" * 66
    print()
    print(header_line)
    print("      GRAVITHERM - REZULTATE COMPARAȚIE FAZA I (MVP 2)")
    print(header_line)
    print(f"{'Metrica':<32} | {'Baseline ON/OFF':<14} | {'Agent RL (PPO)':<14}")
    print("-" * 66)
    print(
        f"{'Conformitate confort (%)':<32} | {baseline_metrics['comfort_compliance_pct']:<14} | {rl_metrics['comfort_compliance_pct']:<14}"
    )
    print(
        f"{'Energie recaptată (Wh)':<32} | {baseline_metrics['total_recaptured_energy_wh']:<14} | {rl_metrics['total_recaptured_energy_wh']:<14}"
    )
    print(
        f"{'Consum rețea (Wh)':<32} | {baseline_metrics['total_grid_energy_wh']:<14} | {rl_metrics['total_grid_energy_wh']:<14}"
    )
    print(
        f"{'Recompensă medie / pas':<32} | {baseline_metrics['mean_reward']:<14} | {rl_metrics['mean_reward']:<14}"
    )
    print(
        f"{'RMSE Temperatură (°C)':<32} | {baseline_metrics['temperature_rmse']:<14} | {rl_metrics['temperature_rmse']:<14}"
    )
    print(header_line)
    print()


if __name__ == "__main__":
    main()
