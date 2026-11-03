"""Wrapper subțire de inferență ONNX - singurul fișier din agent/ care rulează
efectiv pe Raspberry Pi. Dependințe minime: doar onnxruntime + numpy.
"""

import os
import numpy as np
import onnxruntime as ort

from gravitherm.agent.env_adapter import obs_to_array
from gravitherm.config import ONNX_MODEL_PATH
from gravitherm.interfaces import Action, Observation


class PolicyRunner:
    """Rulează inferența modelului ONNX pe Raspberry Pi (sau în simulator)."""

    def __init__(self, model_path: str = ONNX_MODEL_PATH):
        if not os.path.exists(model_path):
            raise FileNotFoundError(
                f"Modelul ONNX nu a fost găsit la calea '{model_path}'. "
                "Vă rugăm să antrenați și să exportați modelul executând mai întâi: "
                "python -m gravitherm.agent.export_onnx"
            )
        self.model_path = model_path
        self.session = ort.InferenceSession(model_path)
        self.input_name = self.session.get_inputs()[0].name

    def act(self, obs: Observation | dict | np.ndarray) -> Action:
        """Primește o observație și returnează acțiunea determinată de modelul ONNX.

        Args:
            obs: Obiect Observation, dict sau ndarray cu 6 elemente.

        Returns:
            Obiect Action(pump_on=bool, pump_speed_pct=float).
        """
        input_array = np.array([obs_to_array(obs)], dtype=np.float32)
        outputs = self.session.run(None, {self.input_name: input_array})

        raw_output = outputs[0]
        if raw_output.ndim > 1:
            raw_output = raw_output[0]

        action_val = raw_output[0] if raw_output.size > 0 else raw_output
        if isinstance(action_val, (bool, np.bool_)):
            pump_on = bool(action_val)
            speed_pct = 100.0 if pump_on else 0.0
        elif isinstance(action_val, (int, np.integer)):
            pump_on = bool(action_val > 0)
            speed_pct = 100.0 if pump_on else 0.0
        else:
            val = float(action_val)
            if val > 1.0:
                speed_pct = float(np.clip(val, 0.0, 100.0))
                pump_on = speed_pct > 0.0
            elif val < 0.0:
                speed_pct = float(np.clip((val + 1.0) / 2.0 * 100.0, 0.0, 100.0))
                pump_on = speed_pct > 0.0
            else:
                pump_on = val >= 0.5
                speed_pct = val * 100.0 if pump_on else 0.0

        return Action(pump_on=pump_on, pump_speed_pct=speed_pct)
