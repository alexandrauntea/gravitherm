"""Adapter Wrapper peste GraviThermEnv pentru integrarea cu Stable-Baselines3.

Extrage datele din Observation, le convertește în vector NumPy de dimensiune (6,)
și calculează recompensa utilizând agent.reward.compute_reward.
"""

import gymnasium as gym
import numpy as np

from gravitherm.agent.reward import RewardWeights, compute_reward
from gravitherm.interfaces import Observation
from gravitherm.simulation.env import GraviThermEnv


def obs_to_array(obs_data) -> np.ndarray:
    """Convertește un dicționar sau un obiect Observation în vector NumPy shape (6,)."""
    if isinstance(obs_data, Observation):
        return np.array(
            [
                obs_data.utl_temperature_c,
                obs_data.pper_pressure_bar,
                obs_data.pper_power_w,
                obs_data.hour_of_day,
                obs_data.energy_price,
                obs_data.hvac_load_w,
            ],
            dtype=np.float32,
        )
    elif isinstance(obs_data, dict):
        return np.array(
            [
                obs_data.get("utl_temperature_c", 0.0),
                obs_data.get("pper_pressure_bar", 0.0),
                obs_data.get("pper_power_w", 0.0),
                obs_data.get("hour_of_day", 0.0),
                obs_data.get("energy_price", 0.0),
                obs_data.get("hvac_load_w", 0.0),
            ],
            dtype=np.float32,
        )
    elif isinstance(obs_data, (list, tuple, np.ndarray)):
        return np.asarray(obs_data, dtype=np.float32)
    else:
        raise TypeError(f"Tip de observație nesuportat: {type(obs_data)}")


def array_to_obs(arr: np.ndarray) -> Observation:
    """Reconstruiește obiectul dataclass Observation dintr-un vector NumPy."""
    flat = np.asarray(arr, dtype=np.float32).flatten()
    if len(flat) != 6:
        raise ValueError(f"Vectorul de observații trebuie să aibă lungimea 6, dar are {len(flat)}")
    return Observation(
        utl_temperature_c=float(flat[0]),
        pper_pressure_bar=float(flat[1]),
        pper_power_w=float(flat[2]),
        hour_of_day=float(flat[3]),
        energy_price=float(flat[4]),
        hvac_load_w=float(flat[5]),
    )


class GraviThermAgentEnv(gym.Env):
    """Wrapper peste GraviThermEnv conform specificațiilor Gymnasium și SB3."""

    def __init__(
        self,
        hvac_noise_std: float = 0.0,
        reward_weights: RewardWeights | None = None,
        continuous_actions: bool = False,
    ):
        super().__init__()
        self.inner_env = GraviThermEnv(hvac_noise_std=hvac_noise_std)
        self.observation_space = gym.spaces.Box(low=-np.inf, high=np.inf, shape=(6,), dtype=np.float32)
        self.continuous_actions = continuous_actions

        if continuous_actions:
            self.action_space = gym.spaces.Box(low=0.0, high=1.0, shape=(1,), dtype=np.float32)
        else:
            self.action_space = self.inner_env.action_space

        self.reward_weights = reward_weights or RewardWeights()

    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        obs_raw, info = self.inner_env.reset(seed=seed, options=options)
        return obs_to_array(obs_raw), info

    def step(self, action):
        if self.continuous_actions:
            act_val = float(np.clip(action, 0.0, 1.0).item() if isinstance(action, np.ndarray) else action)
            discrete_action = 1 if act_val > 0.05 else 0
        else:
            discrete_action = int(action)

        obs_raw, _, terminated, truncated, info = self.inner_env.step(discrete_action)
        if isinstance(obs_raw, dict):
            obs = Observation(**obs_raw)
        elif isinstance(obs_raw, Observation):
            obs = obs_raw
        else:
            obs = array_to_obs(obs_raw)

        grid_import_w = max(0.0, obs.hvac_load_w - obs.pper_power_w)
        reward_breakdown = compute_reward(obs, grid_import_w, weights=self.reward_weights)

        info_dict = dict(info)
        info_dict["reward_breakdown"] = reward_breakdown

        return obs_to_array(obs), float(reward_breakdown.total), terminated, truncated, info_dict
