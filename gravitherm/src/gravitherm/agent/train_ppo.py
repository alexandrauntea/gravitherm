"""Antreneaza agentul PPO (Stable-Baselines3) pe GraviThermAgentEnv.

Rulare: python -m gravitherm.agent.train_ppo [--timesteps 100000] [--save-path models/ppo_gravitherm]
"""

import argparse
import os

from stable_baselines3 import PPO

from gravitherm.agent.env_adapter import GraviThermAgentEnv


def main(
    total_timesteps: int = 100_000,
    save_path: str = "models/ppo_gravitherm",
    learning_rate: float = 3e-4,
    seed: int = 42,
):
    os.makedirs(os.path.dirname(save_path) or ".", exist_ok=True)
    env = GraviThermAgentEnv()
    model = PPO(
        "MlpPolicy",
        env,
        learning_rate=learning_rate,
        seed=seed,
        verbose=1,
    )
    model.learn(total_timesteps=total_timesteps)
    model.save(save_path)
    print(f"Model salvat in {save_path}")
    return model


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Antrenare agent PPO RLAEA")
    parser.add_argument("--timesteps", type=int, default=100_000, help="Număr total de pași")
    parser.add_argument(
        "--save-path", type=str, default="models/ppo_gravitherm", help="Calea de salvare a modelului"
    )
    parser.add_argument("--lr", type=float, default=3e-4, help="Rata de învățare")
    parser.add_argument("--seed", type=int, default=42, help="Seed aleator")
    args = parser.parse_args()

    main(
        total_timesteps=args.timesteps,
        save_path=args.save_path,
        learning_rate=args.lr,
        seed=args.seed,
    )
