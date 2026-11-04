"""Definiția celor 6 faze ale scenariului „O zi în Turnul GraviTherm" și profilurile țintă.

Scenariul comprimă 24 de ore de funcționare într-o prezentare de ~4:40 min,
cu trecere controlată de la tastatură (sau automat prin --auto).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

from gravitherm.demo.demo_config import DemoConfig


@dataclass(frozen=True)
class PhaseDefinition:
    """Configurația unei faze din scenariu."""

    phase_id: int
    name: str
    short_title: str
    start_hour: float  # Ora de pornire în format zecimal (ex: 6.0 = 06:00)
    end_hour: float  # Ora de final
    duration_s: float  # Durata reală în secunde
    pump_mode: Literal["OFF", "ON", "RAMP", "PULSE"]
    peltier_mode: Literal["OFF", "ON"]
    decision_text: str  # Decizia afișată a agentului
    icon: str  # Emoji / simbol pentru UI

    # Puncte de referință temperatură exterior (°C)
    temp_ext_start: float
    temp_ext_end: float

    # Puncte de referință interior RL (°C) - strict în 21.0 - 24.0°C
    temp_int_rl_start: float
    temp_int_rl_end: float

    # Puncte de referință interior Clasic (°C) - cu depășiri peste 24°C la caniculă
    temp_int_classic_mean: float


def get_all_phases(config: DemoConfig | None = None) -> list[PhaseDefinition]:
    """Returnează cele 6 faze ale scenariului configurate conform DemoConfig."""
    cfg = config or DemoConfig()

    return [
        PhaseDefinition(
            phase_id=0,
            name="Noapte, pornire sistem",
            short_title="Faza 0 · Noapte",
            start_hour=0.0,
            end_hour=6.0,
            duration_s=cfg.phase_0_duration_s,
            pump_mode="OFF",
            peltier_mode="ON",
            decision_text="Pre-răcire UTL pe tarif ieftin",
            icon="🌙",
            temp_ext_start=8.0,
            temp_ext_end=13.0,
            temp_int_rl_start=21.8,
            temp_int_rl_end=21.4,
            temp_int_classic_mean=22.0,
        ),
        PhaseDefinition(
            phase_id=1,
            name="Dimineață, sosesc angajații",
            short_title="Faza 1 · Dimineață",
            start_hour=6.0,
            end_hour=10.0,
            duration_s=cfg.phase_1_duration_s,
            pump_mode="RAMP",
            peltier_mode="ON",
            decision_text="Cerere de apă ↑ → recuperare energie PPER",
            icon="🌅",
            temp_ext_start=13.0,
            temp_ext_end=25.0,
            temp_int_rl_start=21.4,
            temp_int_rl_end=22.3,
            temp_int_classic_mean=22.5,
        ),
        PhaseDefinition(
            phase_id=2,
            name="Prânz + caniculă (34°C afară)",
            short_title="Faza 2 · Caniculă 34°C",
            start_hour=10.0,
            end_hour=15.0,
            duration_s=cfg.phase_2_duration_s,
            pump_mode="ON",
            peltier_mode="ON",
            decision_text="Răcire pasivă UTL în loc de chiller",
            icon="☀️",
            temp_ext_start=25.0,
            temp_ext_end=34.0,
            temp_int_rl_start=22.3,
            temp_int_rl_end=23.6,  # Rămâne în confort: atinge 23.6°C la vârful caniculei
            temp_int_classic_mean=24.4,  # Depășește 24°C de 2-3 ori
        ),
        PhaseDefinition(
            phase_id=3,
            name="Vârf de consum rețea" if cfg.fixed_tariff_enabled else "Vârf de tarif",
            short_title="Faza 3 · Vârf cerere" if cfg.fixed_tariff_enabled else "Faza 3 · Vârf tarif",
            start_hour=15.0,
            end_hour=18.0,
            duration_s=cfg.phase_3_duration_s,
            pump_mode="PULSE",
            peltier_mode="OFF",
            decision_text=(
                "Vârf de cerere rețea → prioritizez energia recuperată, minimizez rețeaua"
                if cfg.fixed_tariff_enabled
                else "Tarif maxim → prioritizez energia recuperată, minimizez rețeaua"
            ),
            icon="⚡",
            temp_ext_start=34.0,
            temp_ext_end=28.0,
            temp_int_rl_start=23.6,
            temp_int_rl_end=22.9,
            temp_int_classic_mean=23.6,
        ),
        PhaseDefinition(
            phase_id=4,
            name="Seară, clădirea se golește",
            short_title="Faza 4 · Seară",
            start_hour=18.0,
            end_hour=24.0,
            duration_s=cfg.phase_4_duration_s,
            pump_mode="OFF",
            peltier_mode="OFF",
            decision_text="Ocupare scăzută → standby",
            icon="🌆",
            temp_ext_start=28.0,
            temp_ext_end=20.0,
            temp_int_rl_start=22.9,
            temp_int_rl_end=22.1,
            temp_int_classic_mean=22.3,
        ),
        PhaseDefinition(
            phase_id=5,
            name="Sumar performanță",
            short_title="Faza 5 · Sumar",
            start_hour=24.0,
            end_hour=24.0,
            duration_s=cfg.phase_5_duration_s,
            pump_mode="OFF",
            peltier_mode="OFF",
            decision_text="Validat pe machetă · scalabil la clădiri reale",
            icon="🏆",
            temp_ext_start=20.0,
            temp_ext_end=20.0,
            temp_int_rl_start=22.1,
            temp_int_rl_end=22.1,
            temp_int_classic_mean=22.3,
        ),
    ]


def get_electricity_tariff(sim_hour: float, config: DemoConfig | None = None) -> tuple[float, str, str]:
    """Returnează tariful orar (lei/kWh), categoria și culoarea reprezentativă.

    Suportă atât tarif fix (implicit, e.g. 1.00 leu/kWh), cât și tarif orar dinamic.
    """
    cfg = config or DemoConfig()
    if cfg.fixed_tariff_enabled:
        return cfg.fixed_tariff_lei_kwh, "Tarif fix", "#38bdf8"

    hour = min(max(sim_hour, 0.0), 24.0)

    if hour < 6.0:
        return 0.45, "Ieftin (noapte)", "#10b981"  # Verde
    elif hour < 10.0:
        return 0.85, "Mediu (dimineață)", "#f59e0b"  # Galben/Chihlimbar
    elif hour < 15.0:
        return 1.15, "Ridicat (prânz)", "#f97316"  # Portocaliu
    elif hour < 18.0:
        return 1.70, "VÂRF MAXIM", "#ef4444"  # Roșu intens
    else:
        return 0.90, "Mediu (seară)", "#f59e0b"  # Galben/Chihlimbar


def get_simulated_targets(
    phase: PhaseDefinition,
    fraction_in_phase: float,
    wall_elapsed_in_phase: float,
    config: DemoConfig | None = None,
) -> dict[str, float | bool]:
    """Calculează valorile țintă ale scenariului la un anumit moment din fază."""
    cfg = config or DemoConfig()
    frac = min(max(fraction_in_phase, 0.0), 1.0)

    # 1. Temperatură exterior (profil zi realist cu vârf la caniculă)
    temp_ext = phase.temp_ext_start + frac * (phase.temp_ext_end - phase.temp_ext_start)

    # 2. Temperatură interior RL: rămâne strict în 21.0 - 24.0°C
    temp_int_rl = phase.temp_int_rl_start + frac * (phase.temp_int_rl_end - phase.temp_int_rl_start)

    # 3. Temperatură interior Clasic: oscilație dinte de fierăstrău
    # În Faza 2 (caniculă), depășește 24°C cu 2-3 supracreșteri
    sawtooth = 0.45 * math.sin(frac * 8.0 * math.pi)
    if phase.phase_id == 2:
        # Caniculă: histerezisul clasic întârziat pierde controlul și sare la 24.3 - 24.6°C
        heatwave_overshoot = 0.9 * math.sin(frac * 3.0 * math.pi)
        temp_int_classic = 23.6 + heatwave_overshoot + sawtooth
    elif phase.phase_id == 0:
        temp_int_classic = phase.temp_int_classic_mean + sawtooth
    else:
        temp_int_classic = (
            phase.temp_int_rl_start
            + frac * (phase.temp_int_rl_end - phase.temp_int_rl_start)
            + 0.5
            + sawtooth
        )

    # 4. Sol UTL
    temp_soil = cfg.soil_temp_c
    if phase.phase_id == 0:
        temp_soil -= 0.3 * frac  # Pre-răcire noapte

    # 5. Stare actuatori țintă
    if phase.pump_mode == "OFF":
        pump_target = False
        pump_speed_pct = 0.0
    elif phase.pump_mode == "ON":
        pump_target = True
        pump_speed_pct = 100.0
    elif phase.pump_mode == "RAMP":
        # Rampă PWM de 3s dacă ENA e conectat, altfel direct ON
        ramp_pct = min(100.0, (wall_elapsed_in_phase / max(cfg.pwm_ramp_duration_s, 0.1)) * 100.0)
        pump_target = True
        pump_speed_pct = ramp_pct
    elif phase.pump_mode == "PULSE":
        # Ciclare 8s ON / 4s OFF
        cycle_period = cfg.phase_3_pulse_on_s + cfg.phase_3_pulse_off_s
        cycle_pos = wall_elapsed_in_phase % cycle_period
        pump_target = cycle_pos < cfg.phase_3_pulse_on_s
        pump_speed_pct = 100.0 if pump_target else 0.0
    else:
        pump_target = False
        pump_speed_pct = 0.0

    peltier_target = phase.peltier_mode == "ON"

    # 6. Putere rețea (kW): RL vs. Clasic
    # Calibrat riguros conform propunerii:
    # - Economie energie: ~14% (-10...18%)
    # - Economie cost: ~18-22% (prin pre-răcire noaptea și minim la vârful de tarif de 1.70 lei)
    if phase.phase_id == 0:  # Noapte (00-06)
        grid_rl_kw = 2.60  # Pre-răcire ușoară pe tarif ieftin (0.45 lei)
        grid_classic_kw = 2.00
    elif phase.phase_id == 1:  # Dimineață (06-10)
        grid_rl_kw = 4.50
        grid_classic_kw = 5.00
    elif phase.phase_id == 2:  # Prânz caniculă (10-15)
        grid_rl_kw = 6.40  # Răcire pasivă UTL asistă HVAC -> evită suprasarcina chiller
        grid_classic_kw = 8.20  # Chiller clasic forțat continuu
    elif phase.phase_id == 3:  # Vârf tarif (15-18)
        # Recuperare PPER și descărcare inerție termică pe tariful maxim (1.70 lei)
        grid_rl_kw = 4.90
        grid_classic_kw = 7.00
    elif phase.phase_id == 4:  # Seară (18-24)
        grid_rl_kw = 2.90
        grid_classic_kw = 3.20
    else:  # Faza 5 (Sumar)
        grid_rl_kw = 2.00
        grid_classic_kw = 2.00

    return {
        "temp_ext": temp_ext,
        "temp_int_rl": temp_int_rl,
        "temp_int_classic": temp_int_classic,
        "temp_soil": temp_soil,
        "pump_target": pump_target,
        "pump_speed_pct": pump_speed_pct,
        "peltier_target": peltier_target,
        "grid_rl_kw": grid_rl_kw,
        "grid_classic_kw": grid_classic_kw,
    }
