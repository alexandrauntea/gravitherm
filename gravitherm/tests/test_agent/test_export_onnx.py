import os

from gravitherm.agent.export_onnx import main as export_main
from gravitherm.agent.train_ppo import main as train_main


def test_export_onnx_pipeline(tmp_path):
    model_path = str(tmp_path / "test_ppo")
    onnx_path = str(tmp_path / "test_policy.onnx")

    train_main(total_timesteps=128, save_path=model_path, seed=42)
    export_main(model_path=model_path, onnx_path=onnx_path)

    assert os.path.exists(onnx_path)
    assert os.path.getsize(onnx_path) > 0
