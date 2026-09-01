"""Constante fizice și setpoint-uri partajate de toate modulele.

Modificați aici, nu hardcodați aceleași valori în mai multe fișiere.
"""

# --- Constante fizice ---
WATER_DENSITY_KG_M3 = 1000.0
GRAVITY_M_S2 = 9.81

# --- PPER (Pipe Pressure Energy Recovery) ---
TURBINE_EFFICIENCY = 0.72  # tipic 0.65-0.80 pentru PAT comerciale

# Doua seturi de H/Q, cu roluri DIFERITE - nu le amestecati (vezi docs/decisions.md):
#
# 1) Scenariul REAL (clădire de 20 etaje) - folosit STRICT pentru extrapolarea
#    analitica din raport/prezentare (impact, ROI, CO2), conform strategiei
#    "simulate-then-scale" din propunere. Macheta de laborator NU reproduce
#    fizic aceasta coloana de apa.
PIPE_HEAD_REAL_BUILDING_M = 60.0  # H, cadere hidraulica cladire reala (60-80m pt. 20 etaje)
PIPE_FLOW_REAL_BUILDING_L_S = 0.05  # Q - vezi docs/decisions.md pentru motivarea 0.05 vs 0.5

# 2) Scenariul de LABORATOR (macheta fizica) - H si Q REALE ale montajului
#    vostru (rezervor + tub silicon 6mm + pompa mini DC), NU valorile de mai
#    sus. Raman None pana se masoara fizic macheta (Faza II) - NU inlocuiti
#    cu o presupunere fara sa masurati, si NU refolositi valorile de la
#    cladirea reala aici.
PIPE_HEAD_LAB_M = None  # TODO(Alexandra, Faza II): masurati inaltimea reala rezervor->iesire
PIPE_FLOW_LAB_L_S = (
    None  # TODO(Alexandra, Faza II): calibrati din BMP280, vezi pper_model.pressure_to_flow_estimate_l_s
)

# --- UTL (Underground Thermal Loop) ---
SOIL_UNDISTURBED_TEMP_C = 13.0  # 12-14°C, sol la 5-8m adancime, Romania
SOIL_THERMAL_CONDUCTIVITY = 2.0  # W/(m*K), 1.5-2.5 pt. argila/nisip

# --- Confort termic (folosit de agent/reward.py) ---
COMFORT_TEMP_MIN_C = 21.0
COMFORT_TEMP_MAX_C = 24.0

# --- IoT ---
MQTT_BROKER_HOST = "localhost"
MQTT_BROKER_PORT = 1883
MQTT_TOPIC_PREFIX = "gravitherm"

INFLUXDB_URL = "http://localhost:8086"
INFLUXDB_BUCKET = "gravitherm"
INFLUXDB_ORG = "gravitherm"

# --- Model RL ---
ONNX_MODEL_PATH = "models/rlaea_policy.onnx"
