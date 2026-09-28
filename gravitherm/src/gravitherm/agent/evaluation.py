"""Modul de evaluare și metrici de comparație pentru politicile de control HVAC/UTL."""

from dataclasses import dataclass

import numpy as np

from gravitherm.config import COMFORT_TEMP_MAX_C, COMFORT_TEMP_MIN_C
from gravitherm.interfaces import Action, Observation


@dataclass
class EvaluationMetrics:
    comfort_compliance_pct: float  # % din timp cu temperatura în [21, 24] °C
    total_recaptured_energy_wh: float  # Energie totală PPER generată (Wh)
    total_grid_energy_wh: float  # Energie totală consumată din rețea (Wh)
    mean_reward: float  # Recompensă medie pe pas
    temperature_rmse: float  # RMSE față de setpointul ideal de 22.5 °C

    def to_dict(self) -> dict:
        return {
            "comfort_compliance_pct": round(self.comfort_compliance_pct, 2),
            "total_recaptured_energy_wh": round(self.total_recaptured_energy_wh, 2),
            "total_grid_energy_wh": round(self.total_grid_energy_wh, 2),
            "mean_reward": round(self.mean_reward, 4),
            "temperature_rmse": round(self.temperature_rmse, 3),
        }


class BaselineOnOffPolicy:
    """Controler clasic de termostat cu histerezis."""

    def __init__(self, t_lower: float = 21.5, t_upper: float = 23.5):
        self.t_lower = t_lower
        self.t_upper = t_upper
        self._pump_state = False

    def act(self, obs: Observation) -> Action:
        if obs.utl_temperature_c >= self.t_upper:
            self._pump_state = True
        elif obs.utl_temperature_c <= self.t_lower:
            self._pump_state = False

        return Action(
            pump_on=self._pump_state,
            pump_speed_pct=100.0 if self._pump_state else 0.0,
        )


def evaluate_policy(env, policy, n_steps: int = 1440) -> EvaluationMetrics:
    """Evaluează o politică (Baseline sau RL) pe mediul de simulare."""
    from gravitherm.agent.env_adapter import array_to_obs

    obs_array, _info = env.reset(seed=42)

    rewards = []
    temperatures = []
    recaptured_powers = []
    grid_powers = []

    for _ in range(n_steps):
        obs = array_to_obs(obs_array) if isinstance(obs_array, np.ndarray) else obs_array

        if hasattr(policy, "act"):
            action_obj = policy.act(obs)
        else:
            action_obj = policy(obs)

        if hasattr(env.action_space, "n"):
            if isinstance(action_obj, Action):
                action_env = 1 if action_obj.pump_on else 0
            else:
                action_env = int(action_obj)
        else:
            if isinstance(action_obj, Action):
                speed = action_obj.pump_speed_pct / 100.0
            else:
                speed = float(action_obj)
            action_env = np.array([speed], dtype=np.float32)

        next_obs_array, reward, terminated, truncated, _step_info = env.step(action_env)

        obs_current = (
            array_to_obs(next_obs_array) if isinstance(next_obs_array, np.ndarray) else next_obs_array
        )
        temperatures.append(obs_current.utl_temperature_c)
        recaptured_powers.append(obs_current.pper_power_w)
        grid_powers.append(max(0.0, obs_current.hvac_load_w - obs_current.pper_power_w))
        rewards.append(reward)

        obs_array = next_obs_array
        if terminated or truncated:
            obs_array, _ = env.reset()

    temp_arr = np.array(temperatures)
    comfort_count = np.sum((temp_arr >= COMFORT_TEMP_MIN_C) & (temp_arr <= COMFORT_TEMP_MAX_C))
    comfort_compliance_pct = (comfort_count / len(temp_arr)) * 100.0

    dt_hours = 1.0 / 60.0
    total_recaptured_wh = float(np.sum(recaptured_powers) * dt_hours)
    total_grid_wh = float(np.sum(grid_powers) * dt_hours)
    mean_reward = float(np.mean(rewards))

    ideal_temp = (COMFORT_TEMP_MIN_C + COMFORT_TEMP_MAX_C) / 2.0
    temp_rmse = float(np.sqrt(np.mean((temp_arr - ideal_temp) ** 2)))

    return EvaluationMetrics(
        comfort_compliance_pct=comfort_compliance_pct,
        total_recaptured_energy_wh=total_recaptured_wh,
        total_grid_energy_wh=total_grid_wh,
        mean_reward=mean_reward,
        temperature_rmse=temp_rmse,
    )
