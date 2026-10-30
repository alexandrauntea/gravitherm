"""Wrapper subtire de inferenta ONNX - singurul fisier din agent/ care ruleaza
efectiv pe Raspberry Pi. Dependinte minime: doar onnxruntime + numpy.
"""

import numpy as np
import onnxruntime as ort

from gravitherm.config import ONNX_MODEL_PATH
from gravitherm.interfaces import Action, Observation


class PolicyRunner:
    def __init__(self, model_path: str = ONNX_MODEL_PATH):
        self.session = ort.InferenceSession(model_path)

    def act(self, obs: Observation) -> Action:
        input_array = np.array(
            [
                [
                    obs.utl_temperature_c,
                    obs.pper_pressure_bar,
                    obs.pper_power_w,
                    obs.hour_of_day,
                    obs.energy_price,
                    obs.hvac_load_w,
                ]
            ],
            dtype=np.float32,
        )
        outputs = self.session.run(None, {"observation": input_array})
        pump_on = bool(outputs[0][0] > 0.5)
        return Action(pump_on=pump_on, pump_speed_pct=100.0 if pump_on else 0.0)
