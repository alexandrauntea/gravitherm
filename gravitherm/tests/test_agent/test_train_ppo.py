import os

from gravitherm.agent.train_ppo import main as train_main


def test_train_ppo_short_run(tmp_path):
    save_path = str(tmp_path / "test_ppo")
    train_main(total_timesteps=128, save_path=save_path, seed=42)
    assert os.path.exists(f"{save_path}.zip")
