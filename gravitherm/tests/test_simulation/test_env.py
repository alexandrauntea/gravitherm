from gravitherm.interfaces import Observation
from gravitherm.simulation.env import GraviThermEnv


def test_env_reset_returns_valid_observation():
    """Verifica reset-ul mediului Gymnasium si ca intoarce o observatie conform contractului."""
    env = GraviThermEnv()
    obs_dict, _ = env.reset(seed=42)

    assert isinstance(obs_dict, dict)
    assert "utl_temperature_c" in obs_dict
    assert "pper_pressure_bar" in obs_dict
    assert "pper_power_w" in obs_dict
    assert "hour_of_day" in obs_dict
    assert "energy_price" in obs_dict
    assert "hvac_load_w" in obs_dict
    assert obs_dict["hour_of_day"] == 0.0


def test_env_step_advances_time_and_returns_observation():
    """Verifica factul ca step() avanseaza timpul si respecta campurile din Observation."""
    env = GraviThermEnv()
    env.reset(seed=42)

    obs_dict, _, _, _, _ = env.step(action=1)

    assert isinstance(obs_dict, dict)
    obs = Observation(**obs_dict)
    assert obs.hour_of_day > 0.0
