"""Wrapper subtire de inferenta ONNX - singurul fisier din agent/ care ruleaza
efectiv pe Raspberry Pi. Dependinte minime: doar onnxruntime + numpy.
"""

import numpy as np
import onnxruntime as ort

from gravitherm.agent.env_adapter import obs_to_array
from gravitherm.config import ONNX_MODEL_PATH
from gravitherm.interfaces import Action, Observation


class PolicyRunner:
    def __init__(self, model_path: str = ONNX_MODEL_PATH):
        self.session = ort.InferenceSession(model_path)

    def act(self, obs: Observation) -> Action:
        input_array = np.array([obs_to_array(obs)], dtype=np.float32)
        outputs = self.session.run(None, {"observation": input_array})

        raw_output = outputs[0]
        if raw_output.ndim > 1:
            raw_output = raw_output[0]

        action_val = raw_output[0] if raw_output.size > 0 else raw_output
        pump_on = bool(
            action_val > 0.5 or (isinstance(action_val, (np.int64, int, float)) and action_val >= 0.5)
        )

        return Action(pump_on=pump_on, pump_speed_pct=100.0 if pump_on else 0.0)
