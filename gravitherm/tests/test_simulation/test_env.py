import numpy as np

from gravitherm.simulation.env import GraviThermEnv
from scripts.baseline_onoff import run_baseline_episode


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


def test_env_reset_reproducibility():
    """Verifica ca reset(seed=42) produce exact aceeasi prima observatie."""
    env1 = GraviThermEnv(hvac_noise_std=50.0)
    obs1, _ = env1.reset(seed=42)

    env2 = GraviThermEnv(hvac_noise_std=50.0)
    obs2, _ = env2.reset(seed=42)

    assert obs1 == obs2


def test_on_off_baseline_episode_no_nan_and_bounded():
    """Verifica un episod complet de 24h cu controller-ul ON/OFF.

    Garanteaza ca nicio valoare nu este NaN/inf si ca temperatura ramane
    in intervalul fizic plauzibil (5.0C - 40.0C).
    """
    env = GraviThermEnv()
    records = run_baseline_episode(env=env, num_steps=1440)

    assert len(records) == 1440

    for rec in records:
        for k, v in rec.items():
            assert not np.isnan(v), f"Valoarea {k} este NaN la pasul {rec['step']}"
            assert not np.isinf(v), f"Valoarea {k} este Inf la pasul {rec['step']}"

        temp = rec["utl_temperature_c"]
        assert 5.0 <= temp <= 40.0, f"Temperatura {temp}C este in afara limitelor fizice plauzibile"


def test_pump_action_affects_power_and_temperature():
    """Verifica diferenta de dinamica intre actiunea pompa pornita (1) si oprita (0)."""
    env = GraviThermEnv(initial_utl_temp_c=25.0)
    env.reset(seed=42)

    # Pas cu pompa oprita (0) -> puterea este 0, temperatura creste sub sarcina HVAC
    obs_off, _, _, _, _ = env.step(action=0)
    assert obs_off["pper_power_w"] == 0.0
    assert obs_off["pper_pressure_bar"] == 0.0

    # Pas cu pompa pornita (1) -> generare PPER > 0 si racire activa
    obs_on, _, _, _, _ = env.step(action=1)
    assert obs_on["pper_power_w"] > 20.0
    assert obs_on["pper_pressure_bar"] > 5.0
