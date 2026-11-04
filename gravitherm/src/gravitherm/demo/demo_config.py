"""Configurare și parametri reglabili pentru Demo Live GraviTherm.

Include toți parametrii de hardware, durate de fază, profiluri de tarif și
scalare fizică clădire reală vs. machetă de laborator.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from gravitherm.config import (
    COMFORT_TEMP_MAX_C,
    COMFORT_TEMP_MIN_C,
    DS18B20_COLD_SIDE,
    DS18B20_HOT_SIDE,
    DS18B20_RESERVOIR,
    GPIO_1WIRE,
    GPIO_PELTIER,
    GPIO_PUMP_ENA,
    GPIO_PUMP_IN1,
    GPIO_PUMP_IN2,
    HOT_SIDE_LIMIT_C,
    HOT_SIDE_WARN_C,
    MQTT_BROKER_HOST,
    MQTT_BROKER_PORT,
    MQTT_TOPIC_PREFIX,
    PIPE_FLOW_REAL_BUILDING_L_S,
    PIPE_HEAD_REAL_BUILDING_M,
    SOIL_UNDISTURBED_TEMP_C,
    TURBINE_EFFICIENCY,
)


@dataclass
class DemoConfig:
    """Configurație completă reglabilă pentru demo-ul live."""

    # --- Siguranță & Stare Pompă ---
    # Implicit False pentru a proteja pompa împotriva mersului în gol pe birou.
    # Se poate activa la pornire prin parametrul CLI `--enable-pump` sau din dashboard.
    pump_enabled: bool = False

    # --- Pini GPIO și Adrese Senzori (din config.py / hardware real) ---
    gpio_peltier: int = GPIO_PELTIER  # GPIO25 (MOSFET poartă Peltier)
    gpio_pump_in1: int = GPIO_PUMP_IN1  # GPIO23 (L298N IN1)
    gpio_pump_in2: int = GPIO_PUMP_IN2  # GPIO24 (L298N IN2)
    gpio_pump_ena: int | None = GPIO_PUMP_ENA  # None dacă e jumperat 100%
    gpio_1wire: int = GPIO_1WIRE  # GPIO4 (DS18B20 1-Wire)

    # Roluri senzori DS18B20
    ds18b20_roles: dict[str, str] = field(
        default_factory=lambda: {
            "cold_side": DS18B20_COLD_SIDE,
            "reservoir": DS18B20_RESERVOIR,
            "hot_side": DS18B20_HOT_SIDE,
        }
    )

    # --- Protecții Hardware & Watchdog ---
    watchdog_timeout_s: float = 3.0  # Oprire de urgență dacă motorul nu bate în 3s
    peltier_max_continuous_s: float = 300.0  # Decuplare automată Peltier după 5 min
    peltier_hot_warn_c: float = HOT_SIDE_WARN_C  # 50.0°C
    peltier_hot_limit_c: float = HOT_SIDE_LIMIT_C  # 60.0°C oprire urgență delaminare

    # --- Faze Demo: Durate în secunde (ajustabile) ---
    phase_0_duration_s: float = 25.0  # 00:00 -> 06:00 (Noapte, pre-răcire)
    phase_1_duration_s: float = 70.0  # 06:00 -> 10:00 (Dimineață, sosire angajați)
    phase_2_duration_s: float = 80.0  # 10:00 -> 15:00 (Prânz, caniculă 34°C)
    phase_3_duration_s: float = 50.0  # 15:00 -> 18:00 (Vârf de tarif, pulsuri)
    phase_4_duration_s: float = 25.0  # 18:00 -> 24:00 (Seară, plecare angajați)
    phase_5_duration_s: float = 30.0  # 24:00 (Sumar final impact & scalare)

    # --- Parametri Puls Faza 3 ---
    phase_3_pulse_on_s: float = 8.0  # Pompă pornită 8 secunde
    phase_3_pulse_off_s: float = 4.0  # Pompă oprită 4 secunde

    # --- Rampa PWM Faza 1 ---
    pwm_ramp_duration_s: float = 3.0  # Răspuns rampă 0 -> 100% dacă ENA este pe PWM

    # --- Rate de eșantionare ---
    engine_tick_hz: float = 2.0  # Rata mașinii de stări și a modelului de date (~2 Hz)
    dashboard_interval_ms: int = 1000  # Interval reactivare Dash (1s)

    # --- Model Presiune & Hidraulică Machetă ---
    pipe_pressure_max_kpa: float = 18.0  # Presiune nominală pe coloană pompă ON
    pipe_pressure_tau_rise_s: float = 1.5  # Constanta de timp ordin 1 creștere presiune
    pipe_pressure_tau_fall_s: float = 1.0  # Constanta de timp scădere presiune
    pipe_pressure_ripple_kpa: float = 0.3  # Variație mică de flux (ripple)

    lab_flow_nominal_l_min: float = 1.5  # Debit nominal pe machetă (~0.025 L/s)
    lab_head_m: float = 0.35  # Înălțime cădere coloană machetă (~35 cm)
    turbine_efficiency: float = TURBINE_EFFICIENCY  # 0.72

    # --- Extrapolare Clădire Reală (Simulate-then-scale) ---
    building_head_m: float = PIPE_HEAD_REAL_BUILDING_M  # 60.0 m (12-20 etaje)
    building_flow_l_s: float = PIPE_FLOW_REAL_BUILDING_L_S  # 0.05 L/s (docs/decisions.md)
    building_hvac_base_kw: float = 12.0  # Putere de bază instalație răcire clădire
    building_co2_kg_kwh: float = 0.26  # Factor emisii rețea România (0.26 kg CO2/kWh)

    # --- Confort Termic & Temperaturi Sol ---
    comfort_min_c: float = COMFORT_TEMP_MIN_C  # 21.0°C
    comfort_max_c: float = COMFORT_TEMP_MAX_C  # 24.0°C
    soil_temp_c: float = SOIL_UNDISTURBED_TEMP_C  # 13.0°C

    # --- Tarif Energie (Fix vs Dinamic) ---
    fixed_tariff_enabled: bool = True  # Implicit tarif fix (la cererea echipei)
    fixed_tariff_lei_kwh: float = 1.00  # Valoare fixă: 1.00 leu / kWh

    # --- Netezire Senzori (Filtru Ordin 1) ---
    temp_filter_tau_s: float = 4.0  # Filtru ordin 1 pentru treceri line fără salturi
    temp_noise_std_c: float = 0.05  # Zgomot gaussian realist

    # --- MQTT (Opțional, fallback silențios) ---
    mqtt_enabled: bool = True
    mqtt_host: str = MQTT_BROKER_HOST
    mqtt_port: int = MQTT_BROKER_PORT
    mqtt_prefix: str = MQTT_TOPIC_PREFIX

    # --- Server Web Dashboard ---
    server_host: str = "0.0.0.0"
    server_port: int = 8050


# Instanță globală singleton configurabilă
DEFAULT_DEMO_CONFIG = DemoConfig()
