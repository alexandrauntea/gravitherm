from gravitherm.agent.export_onnx import main as export_main
from gravitherm.agent.inference import PolicyRunner
from gravitherm.agent.train_ppo import main as train_main
from gravitherm.interfaces import Action, Observation


def test_inference_with_exported_model(tmp_path):
    model_path = str(tmp_path / "test_ppo")
    onnx_path = str(tmp_path / "test_policy.onnx")

    train_main(total_timesteps=128, save_path=model_path, seed=42)
    export_main(model_path=model_path, onnx_path=onnx_path)

    runner = PolicyRunner(model_path=onnx_path)
    obs = Observation(
        utl_temperature_c=22.0,
        pper_pressure_bar=1.0,
        pper_power_w=20.0,
        hour_of_day=12.0,
        energy_price=0.4,
        hvac_load_w=100.0,
    )
    action = runner.act(obs)
    assert isinstance(action, Action)
    assert isinstance(action.pump_on, bool)
    assert action.pump_speed_pct in (0.0, 100.0)
