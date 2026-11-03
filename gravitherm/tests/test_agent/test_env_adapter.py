import numpy as np

from gravitherm.agent.env_adapter import GraviThermAgentEnv, array_to_obs, obs_to_array
from gravitherm.interfaces import Observation


def test_obs_conversion_roundtrip():
    obs = Observation(
        utl_temperature_c=22.5,
        pper_pressure_bar=1.2,
        pper_power_w=15.0,
        hour_of_day=14.5,
        energy_price=0.3,
        hvac_load_w=45.0,
    )
    arr = obs_to_array(obs)
    assert isinstance(arr, np.ndarray)
    assert arr.shape == (6,)

    obs_reconstructed = array_to_obs(arr)
    assert obs_reconstructed.utl_temperature_c == obs.utl_temperature_c
    assert obs_reconstructed.hvac_load_w == obs.hvac_load_w


def test_agent_env_step():
    env = GraviThermAgentEnv()
    obs, _info = env.reset(seed=42)
    assert isinstance(obs, np.ndarray)
    assert obs.shape == (6,)

    next_obs, reward, _terminated, _truncated, step_info = env.step(action=1)
    assert isinstance(next_obs, np.ndarray)
    assert isinstance(reward, float)
    assert "reward_breakdown" in step_info
