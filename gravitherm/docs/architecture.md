# Arhitectura tehnică a prototipului

Cele 3 straturi din propunere, mapate pe cod:

```
┌─────────────────────────────────────────────────────────────┐
│ Strat 1: Simulare (Software Core)                            │
│  src/gravitherm/simulation/  — modele UTL, PPER, HVAC (NumPy/│
│  SciPy) + mediu Gymnasium pentru antrenare RL                │
└───────────────────────────┬───────────────────────────────────┘
                             │ interfaces.py::Observation
┌───────────────────────────▼───────────────────────────────────┐
│ Strat 2: Agent RL (RLAEA)                                      │
│  src/gravitherm/agent/ — reward multi-obiectiv, antrenare PPO/ │
│  SAC (Stable-Baselines3), export ONNX (~2MB)                   │
└───────────────────────────┬───────────────────────────────────┘
                             │ inference.py (onnxruntime)
┌───────────────────────────▼───────────────────────────────────┐
│ Strat 3: IoT (Hardware Edge + Pipeline de date)                │
│  src/gravitherm/iot/ — senzori (DS18B20, BMP280), actuatoare   │
│  (pompă L298N, LED), MQTT (Mosquitto) → InfluxDB → Grafana     │
│  Rulează pe Raspberry Pi 4, alimentat (la scară reală) de PPER │
└─────────────────────────────────────────────────────────────┘
```

`src/gravitherm/dashboard/` (Plotly Dash) citește atât din simulare (Faza I) cât și, ulterior, din InfluxDB (Faza III), pentru a compara agentul RL cu baseline-ul ON/OFF.

Detalii complete despre fiecare ecuație și componentă: `docs/plan.md` și documentul de propunere din proiect.
