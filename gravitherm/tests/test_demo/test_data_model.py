"""Teste de integrare pentru modelul de date și dinamica fizică a demo-ului."""

import pytest

from gravitherm.demo.data_model import DataModel
from gravitherm.demo.demo_config import DemoConfig
from gravitherm.demo.scenario import get_all_phases


def test_full_day_simulation_and_metrics():
    """Simulează o zi completă (faza 0 -> faza 5) și verifică toate cerințele demo-ului."""
    cfg = DemoConfig()
    model = DataModel(config=cfg, mock_mode=True)
    phases = get_all_phases(cfg)

    dt_s = 0.5  # 2 Hz
    classic_overshoot_detected = False

    for phase in phases:
        steps_count = int(phase.duration_s / dt_s)
        if steps_count == 0:
            steps_count = 1

        for step_i in range(steps_count):
            wall_elapsed = step_i * dt_s
            frac = wall_elapsed / max(phase.duration_s, 0.1)
            sim_hour = phase.start_hour + frac * (phase.end_hour - phase.start_hour)

            # Comandă simulat pompă/peltier conform modului
            pump_on = phase.pump_mode in ("ON", "RAMP") or (
                phase.pump_mode == "PULSE" and (wall_elapsed % 12.0) < 8.0
            )
            peltier_on = phase.peltier_mode == "ON"

            pt = model.step(
                phase=phase,
                fraction_in_phase=frac,
                wall_elapsed_in_phase=wall_elapsed,
                sim_hour=sim_hour,
                dt_s=dt_s,
                actual_pump_on=pump_on,
                actual_pump_speed_pct=100.0 if pump_on else 0.0,
                actual_peltier_on=peltier_on,
            )

            # 1. Regula de confort: Agentul RL TREBUIE să rămână în 21.0 - 24.0°C
            assert (
                21.0 <= pt.temp_int_rl <= 24.0
            ), f"Temperatura RL {pt.temp_int_rl:.2f}°C a ieșit din confort în faza {phase.phase_id}!"

            # 2. Controlul clasic depășește 24.0°C la caniculă (faza 2)
            if phase.phase_id == 2 and pt.temp_int_classic > 24.0:
                classic_overshoot_detected = True

            # 3. Presiunea crește în fazele continue când pompa e pornită
            if phase.phase_id in (1, 2) and wall_elapsed > 5.0:
                assert pt.pressure_kpa > 10.0
            elif phase.phase_id in (0, 4) and wall_elapsed > 5.0:
                assert pt.pressure_kpa < 2.0

    assert classic_overshoot_detected, "Controlul clasic trebuia să prezinte depășiri peste 24°C la caniculă!"

    summary = model.get_summary_metrics()

    # 4. Economia de energie: target în intervalul propus (10 - 25%, centrat pe ~14%)
    energy_savings = summary["energy_savings_pct"]
    assert (
        10.0 <= energy_savings <= 25.0
    ), f"Economia de energie {energy_savings:.1f}% este în afara intervalului 10-25%!"

    # 5. Economia de cost: la tarif fix este egală cu economia de energie (~13.7%),
    # iar la tarif dinamic este centrată pe ~18-22%.
    cost_savings = summary["cost_savings_pct"]
    if cfg.fixed_tariff_enabled:
        assert cost_savings == pytest.approx(energy_savings, abs=0.1)
        assert 10.0 <= cost_savings <= 25.0
    else:
        assert 15.0 <= cost_savings <= 26.0

    # 6. Energie recuperată PPER pozitivă
    assert summary["energy_pper_lab_wh"] > 0.0
    assert summary["energy_pper_real_kwh_day"] > 0.0

    # 7. Confort RL superior controlului clasic
    assert summary["comfort_pct_rl"] >= 99.0
    assert summary["comfort_pct_classic"] < summary["comfort_pct_rl"]

    model.close()


def test_dynamic_tariff_cost_arbitrage():
    """Verifică faptul că pe tarif dinamic arbitrajul orar produce economii de cost superioare (15-26%)."""
    cfg = DemoConfig(fixed_tariff_enabled=False)
    model = DataModel(config=cfg, mock_mode=True)
    phases = get_all_phases(cfg)

    dt_s = 0.5
    for phase in phases:
        steps_count = max(1, int(phase.duration_s / dt_s))
        for step_i in range(steps_count):
            wall_elapsed = step_i * dt_s
            frac = wall_elapsed / max(phase.duration_s, 0.1)
            sim_hour = phase.start_hour + frac * (phase.end_hour - phase.start_hour)
            pump_on = phase.pump_mode in ("ON", "RAMP") or (
                phase.pump_mode == "PULSE" and (wall_elapsed % 12.0) < 8.0
            )
            peltier_on = phase.peltier_mode == "ON"
            model.step(
                phase=phase,
                fraction_in_phase=frac,
                wall_elapsed_in_phase=wall_elapsed,
                sim_hour=sim_hour,
                dt_s=dt_s,
                actual_pump_on=pump_on,
                actual_pump_speed_pct=100.0 if pump_on else 0.0,
                actual_peltier_on=peltier_on,
            )

    summary = model.get_summary_metrics()
    cost_savings = summary["cost_savings_pct"]
    assert 15.0 <= cost_savings <= 26.0
    model.close()


def test_pressure_and_hydraulic_response():
    """Verifică răspunsul dinamic al presiunii și debitului."""
    cfg = DemoConfig()
    model = DataModel(config=cfg, mock_mode=True)
    phases = get_all_phases(cfg)
    phase_1 = phases[1]  # Dimineață, pompă ON

    # Răspuns la pornire pompă
    for step in range(10):
        pt = model.step(
            phase=phase_1,
            fraction_in_phase=0.1,
            wall_elapsed_in_phase=step * 0.5,
            sim_hour=6.5,
            dt_s=0.5,
            actual_pump_on=True,
            actual_pump_speed_pct=100.0,
            actual_peltier_on=True,
        )

    # Presiunea trebuie să fie în creștere spre 18 kPa
    assert pt.pressure_kpa > 12.0
    assert pt.flow_l_min > 1.0
    assert pt.power_pper_extrapolated_w > 18.0

    model.close()
