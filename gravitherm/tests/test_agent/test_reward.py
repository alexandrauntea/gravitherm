from gravitherm.agent.reward import RewardWeights, compute_reward
from gravitherm.interfaces import Observation


def test_comfort_is_maximal_in_range():
    obs = Observation(
        utl_temperature_c=22.0,
        pper_pressure_bar=1.0,
        pper_power_w=10.0,
        hour_of_day=12.0,
        energy_price=0.5,
        hvac_load_w=50.0,
    )
    breakdown = compute_reward(obs, grid_import_w=40.0)
    assert breakdown.comfort == 1.0
    assert breakdown.discomfort_penalty == 0.0


def test_discomfort_penalty_outside_range():
    obs = Observation(
        utl_temperature_c=30.0,
        pper_pressure_bar=0.0,
        pper_power_w=0.0,
        hour_of_day=12.0,
        energy_price=0.5,
        hvac_load_w=0.0,
    )
    breakdown = compute_reward(obs, grid_import_w=0.0)
    assert breakdown.comfort == 0.0
    assert abs(breakdown.discomfort_penalty - 0.6) < 1e-5


def test_reward_weights_customization():
    obs = Observation(
        utl_temperature_c=22.0,
        pper_pressure_bar=1.0,
        pper_power_w=10.0,
        hour_of_day=12.0,
        energy_price=0.0,
        hvac_load_w=0.0,
    )
    weights = RewardWeights(w_comfort=2.0, w_recaptured=0.1, w_price=0.5)
    breakdown = compute_reward(obs, grid_import_w=0.0, weights=weights)
    assert breakdown.comfort == 2.0
    assert breakdown.recaptured_energy_bonus == 1.0
    assert breakdown.price_bonus == 0.5
