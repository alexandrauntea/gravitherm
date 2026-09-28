import numpy as np

from gravitherm.simulation.env import GraviThermEnv
from scripts.baseline_onoff import on_off_controller, run_baseline_episode


def test_env_reset_return_valid_observation():
    """Verifica reset-ul mediului Gymnasium si ca intoarce o observation conform contractului."""
    env1 = GraviThermEnv()
    obs_dict, _ = env1.reset(seed=42)

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
        assert 5.0 <= temp <= 40.0, f"Temperatura {temp}C este in afara limitelor fizice plauzibilit"


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


def test_env_stochastic_long_term_stability():
    """Testeaza 10.000 de pasi simulati cu zgomot HVAC stocastic (std=100W)."""
    env = GraviThermEnv(hvac_noise_std=100.0)
    obs_dict, _ = env.reset(seed=42)
    pump_on_count = 0

    for step_idx in range(1, 10_001):
        temp_c = obs_dict["utl_temperature_c"]
        if step_idx % 2 == 0:
            action = int(env.action_space.sample())
        else:
            action = on_off_controller(current_temp_c=temp_c, pump_is_on=(bool(pump_on_count > 0)))

        obs_dict, _, terminated, truncated, _ = env.step(action)

        for key, val in obs_dict.items():
            assert not np.isnan(val), f"NaN la pasul {step_idx} pentru {key}"
            assert not np.isinf(val), f"Inf la pasul {step_idx} pentru {key}"

        if terminated or truncated:
            obs_dict, _ = env.reset()

    assert 5.0 <= obs_dict["utl_temperature_c"] <= 40.0
