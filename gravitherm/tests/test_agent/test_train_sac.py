import os

from gravitherm.agent.train_sac import main as train_sac_main


def test_train_sac_short_run(tmp_path):
    save_path = str(tmp_path / "test_sac")
    train_sac_main(total_timesteps=128, save_path=save_path, seed=42)
    assert os.path.exists(f"{save_path}.zip")
