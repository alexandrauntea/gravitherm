from gravitherm.agent.env_adapter import GraviThermAgentEnv
from gravitherm.agent.evaluation import BaselineOnOffPolicy, EvaluationMetrics, evaluate_policy
from gravitherm.interfaces import Observation


def test_baseline_policy_hysteresis():
    policy = BaselineOnOffPolicy(t_lower=21.5, t_upper=23.5)

    obs_low = Observation(
        utl_temperature_c=20.0,
        pper_pressure_bar=0.0,
        pper_power_w=0.0,
        hour_of_day=12.0,
        energy_price=0.5,
        hvac_load_w=0.0,
    )
    act1 = policy.act(obs_low)
    assert not act1.pump_on

    obs_high = Observation(
        utl_temperature_c=24.0,
        pper_pressure_bar=0.0,
        pper_power_w=0.0,
        hour_of_day=12.0,
        energy_price=0.5,
        hvac_load_w=0.0,
    )
    act2 = policy.act(obs_high)
    assert act2.pump_on


def test_evaluate_policy_metrics():
    env = GraviThermAgentEnv()
    policy = BaselineOnOffPolicy()
    metrics = evaluate_policy(env, policy, n_steps=60)

    assert isinstance(metrics, EvaluationMetrics)
    assert 0.0 <= metrics.comfort_compliance_pct <= 100.0
    assert metrics.total_recaptured_energy_wh >= 0.0
    assert metrics.total_grid_energy_wh >= 0.0
