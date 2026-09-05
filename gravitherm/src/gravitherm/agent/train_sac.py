"""Antrenare agent SAC (Soft Actor-Critic) pe GraviThermAgentEnv cu acțiune continuă.

Rulare: python -m gravitherm.agent.train_sac [--timesteps 50000] [--save-path models/sac_gravitherm]
"""

import argparse
import os

from stable_baselines3 import SAC

from gravitherm.agent.env_adapter import GraviThermAgentEnv


def main(
    total_timesteps: int = 50_000,
    save_path: str = "models/sac_gravitherm",
    learning_rate: float = 3e-4,
    seed: int = 42,
):
    os.makedirs(os.path.dirname(save_path) or ".", exist_ok=True)
    env = GraviThermAgentEnv(continuous_actions=True)
    model = SAC(
        "MlpPolicy",
        env,
        learning_rate=learning_rate,
        seed=seed,
        verbose=1,
    )
    model.learn(total_timesteps=total_timesteps)
    model.save(save_path)
    print(f"Model SAC salvat în {save_path}")
    return model


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Antrenare agent SAC RLAEA")
    parser.add_argument("--timesteps", type=int, default=50_000, help="Număr total de pași")
    parser.add_argument(
        "--save-path", type=str, default="models/sac_gravitherm", help="Calea de salvare a modelului"
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
