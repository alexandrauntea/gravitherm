from gravitherm.agent.reward import compute_reward
from gravitherm.interfaces import Observation


def test_comfort_is_maximal_in_range():
    obs = Observation(
        utl_temperature_c=22.0,  # in intervalul 21-24C
        pper_pressure_bar=0.0,
        pper_power_w=0.0,
        hour_of_day=12.0,
        energy_price=0.5,
        hvac_load_w=0.0,
    )
    breakdown = compute_reward(obs, grid_import_w=0.0)
    assert breakdown.comfort == 1.0
    assert breakdown.discomfort_penalty == 0.0


def test_discomfort_penalty_outside_range():
    obs = Observation(
        utl_temperature_c=30.0,  # in afara intervalului de confort
        pper_pressure_bar=0.0,
        pper_power_w=0.0,
        hour_of_day=12.0,
        energy_price=0.5,
        hvac_load_w=0.0,
    )
    breakdown = compute_reward(obs, grid_import_w=0.0)
    assert breakdown.comfort == 0.0
    assert breakdown.discomfort_penalty > 0.0
