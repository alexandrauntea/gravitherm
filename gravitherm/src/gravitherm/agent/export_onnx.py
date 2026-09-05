"""Exporta policy-ul PPO antrenat ca model ONNX (~2MB tinta) pentru Raspberry Pi.

Rulare: python -m gravitherm.agent.export_onnx [--model-path models/ppo_gravitherm] [--onnx-path models/rlaea_policy.onnx]
"""

import argparse
import os

import torch
from stable_baselines3 import PPO
from torch import nn

from gravitherm.config import ONNX_MODEL_PATH


class OnnxablePolicy(nn.Module):
    def __init__(self, policy):
        super().__init__()
        self.policy = policy

    def forward(self, observation):
        actions, _, _ = self.policy(observation)
        return actions


def main(model_path: str = "models/ppo_gravitherm", onnx_path: str = ONNX_MODEL_PATH):
    os.makedirs(os.path.dirname(onnx_path) or ".", exist_ok=True)
    model = PPO.load(model_path)
    onnxable = OnnxablePolicy(model.policy)
    onnxable.eval()

    dummy_input = torch.randn(1, 6, dtype=torch.float32)

    torch.onnx.export(
        onnxable,
        dummy_input,
        onnx_path,
        input_names=["observation"],
        output_names=["action"],
        opset_version=17,
        dynamo=False,
    )
    print(f"Model ONNX exportat cu succes in {onnx_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export model PPO în format ONNX")
    parser.add_argument(
        "--model-path", type=str, default="models/ppo_gravitherm", help="Calea modelului antrenat SB3"
    )
    parser.add_argument("--onnx-path", type=str, default=ONNX_MODEL_PATH, help="Calea de ieșire fișier .onnx")
    args = parser.parse_args()

    main(model_path=args.model_path, onnx_path=args.onnx_path)
