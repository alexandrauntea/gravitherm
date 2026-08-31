"""Antreneaza agentul PPO (Stable-Baselines3) pe GraviThermEnv.

Rulare: python -m gravitherm.agent.train_ppo
"""

from stable_baselines3 import PPO

from gravitherm.simulation.env import GraviThermEnv


def main(total_timesteps: int = 100_000, save_path: str = "models/ppo_gravitherm"):
    env = GraviThermEnv()
    model = PPO("MlpPolicy", env, verbose=1)
    model.learn(total_timesteps=total_timesteps)
    model.save(save_path)
    print(f"Model salvat in {save_path}")


if __name__ == "__main__":
    main()
