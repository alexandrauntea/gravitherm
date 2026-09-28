"""Mediul Gymnasium care combina UTL + PPER + HVAS intr-o bucla de simulare.

Acesta e fisierul-granita catre agent/ - respecta interfaces.py::Observation.
"""

import gymnasium as gym
import numpy as np

from gravitherm.config import (
    PIPE_FLOW_REAL_BUILDING_L_S,
    PIPE_HEAD_REAL_BUILDING_M,
    SOIL_UNDISTURBED_TEMP_C,
)
from gravitherm.interfaces import Observation
from gravitherm.simulation.hvac_profile import hvac_load_w
from gravitherm.simulation.pper_model import pper_power_w


def hourly_energy_price(hour_of_day: float) -> float:
    """Calculeaza tariful orar normalizat de energie [0.2 - 1.0].
    Tarif maxim la orele de zi (08:00 - 20:00), tarif redus noaptea.
    """
    if 8.0 <= hour_of_day <= 20.0:
        return 1.0
    elif 22.0 <= hour_of_day or hour_of_day <= 6.0:
        return 0.2
    else:
        return 0.6


class GraviThermEnv(gym.Env):
    """Mediu Gymnasium pentru simularea GraviTherm.

    Simuleaza dinamica cuplata a buclei termice UTL, recuperarii PPER
    si profilului HVAC pe un pas de timp de 1 minut (dt = 60s).
    """

    def __init__(
        self,
        hvac_noise_std: float = 0.0,
        initial_utl_temp_c: float = 22.0,
        head_m: float = PIPE_HEAD_REAL_BUILDING_M,
        flow_rate_l_s: float = PIPE_FLOW_REAL_BUILDING_L_S,
    ):
        super().__init__()
        self.observation_space = gym.spaces.Box(low=-np.inf, high=np.inf, shape=(6,), dtype=np.float32)
        self.action_space = gym.spaces.Discrete(2)  # 0 = pump off, 1 = pump on

        self.hvac_noise_std = hvac_noise_std
        self.initial_utl_temp_c = initial_utl_temp_c
        self.head_m = head_m
        self.flow_rate_l_s = flow_rate_l_s
        self._hour = 0.0
        self._utl_temp_c = initial_utl_temp_c
        self._rng = np.random.default_rng()

    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        if seed is not None:
            self._rng = np.random.default_rng(seed)
        self._hour = 0.0
        self._utl_temp_c = self.initial_utl_temp_c
        return self._observation().__dict__, {}

    def step(self, action: int):
        pump_on = bool(action == 1)

        # 1. Calcul debit, presiune si putere PPER
        if pump_on:
            flow_l_s = self.flow_rate_l_s
            pper_power = pper_power_w(flow_rate_l_s=flow_l_s, head_m=self.head_m)
            pper_pressure = self.head_m / 10.197  # converteste metri coloana apa in bar
        else:
            flow_l_s = 0.0
            pper_power = 0.0
            pper_pressure = 0.0

        # 2. Dinamica termica UTL (pas de 1 minut = 60s)
        hvac_load = hvac_load_w(hour_of_day=self._hour, noise_std=self.hvac_noise_std, rng=self._rng)
        heat_gain_rate = (hvac_load / 3000.0) * 0.05  # C/min din consum HVAC

        if pump_on:
            # Pompa raceste bucla spre temperatura neperturbata a solului (13C)
            cooling_rate = (self._utl_temp_c - SOIL_UNDISTURBED_TEMP_C) * 0.08  # C/min
            self._utl_temp_c += heat_gain_rate - cooling_rate
        else:
            # Pompa este oprita, bucla acumuleaza caldura
            self._utl_temp_c += heat_gain_rate

        # 3. Avanseaza timpul cu 1 minut (1/60 ore)
        self._hour = (self._hour + 1.0 / 60.0) % 24.0

        obs = self._observation_with_params(
            pper_pressure_bar=pper_pressure,
            pper_power_w=pper_power,
            hvac_load=hvac_load,
        )

        reward = 0.0  # reward-ul real se calculeaza in agent/reward.py
        terminated = False
        truncated = bool(np.isclose(self._hour, 0.0, atol=1e-5))

        return obs.__dict__, reward, terminated, truncated, {}

    def _observation(self) -> Observation:
        hvac_load = hvac_load_w(hour_of_day=self._hour, noise_std=self.hvac_noise_std, rng=self._rng)
        return self._observation_with_params(
            pper_pressure_bar=0.0,
            pper_power_w=0.0,
            hvac_load=hvac_load,
        )

    def _observation_with_params(
        self, pper_pressure_bar: float, pper_power_w: float, hvac_load: float
    ) -> Observation:
        price = hourly_energy_price(self._hour)
        return Observation(
            utl_temperature_c=float(self._utl_temp_c),
            pper_pressure_bar=float(pper_pressure_bar),
            pper_power_w=float(pper_power_w),
            hour_of_day=float(self._hour),
            energy_price=float(price),
            hvac_load_w=float(hvac_load),
        )
