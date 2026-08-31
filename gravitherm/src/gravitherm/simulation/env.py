"""Mediul Gymnasium care combina UTL + PPER + HVAC intr-o bucla de simulare.

Acesta e fisierul-granita catre agent/ - respecta interfaces.py::Observation.
"""

import gymnasium as gym
import numpy as np

from gravitherm.interfaces import Observation


class GraviThermEnv(gym.Env):
    """Mediu simplificat pentru antrenarea agentului RLAEA.

    TODO(Alexandra + Alina, impreuna): confirmati definitiv observation_space
    si action_space inainte de a incepe train_ppo.py - schimbarile ulterioare
    obliga re-antrenare completa.
    """

    def __init__(self):
        super().__init__()
        self.observation_space = gym.spaces.Box(low=-np.inf, high=np.inf, shape=(6,), dtype=np.float32)
        self.action_space = gym.spaces.Discrete(2)  # 0 = pump off, 1 = pump on
        self._hour = 0.0

    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        self._hour = 0.0
        return self._observation().__dict__, {}

    def step(self, action):
        # TODO(Alexandra): implementati dinamica reala (integrare pas cu pas
        # a modelelor UTL/PPER in functie de actiunea curenta).
        self._hour = (self._hour + 1 / 60) % 24
        obs = self._observation()
        reward = 0.0  # placeholder - reward-ul real vine din agent/reward.py
        terminated = False
        truncated = self._hour == 0.0
        return obs.__dict__, reward, terminated, truncated, {}

    def _observation(self) -> Observation:
        return Observation(
            utl_temperature_c=13.0,
            pper_pressure_bar=0.0,
            pper_power_w=0.0,
            hour_of_day=self._hour,
            energy_price=0.5,
            hvac_load_w=0.0,
        )
