"""Exporta policy-ul PPO antrenat ca model ONNX (~2MB tinta) pentru Raspberry Pi.

Rulare: python -m gravitherm.agent.export_onnx
"""

import torch
from stable_baselines3 import PPO

from gravitherm.config import ONNX_MODEL_PATH


def main(model_path: str = "models/ppo_gravitherm", onnx_path: str = ONNX_MODEL_PATH):
    model = PPO.load(model_path)
    dummy_input = torch.randn(1, 6)  # trebuie sa corespunda observation_space (6 campuri, vezi interfaces.py)
    torch.onnx.export(
        model.policy,
        dummy_input,
        onnx_path,
        input_names=["observation"],
        output_names=["action"],
        opset_version=17,
    )
    print(f"Model ONNX exportat in {onnx_path}")


if __name__ == "__main__":
    main()
