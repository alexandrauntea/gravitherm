"""Teste unitare pentru definiția scenariului și profilurile țintă."""

import pytest

from gravitherm.demo.demo_config import DemoConfig
from gravitherm.demo.scenario import get_all_phases, get_electricity_tariff, get_simulated_targets


def test_phases_sequence_and_hours():
    """Verifică ordinea celor 6 faze și continuitatea orelor simulate."""
    phases = get_all_phases()
    assert len(phases) == 6

    # Verificare id-uri 0..5 în ordine
    for i, phase in enumerate(phases):
        assert phase.phase_id == i

    # Continuitate ore 00:00 -> 24:00
    assert phases[0].start_hour == 0.0
    for i in range(len(phases) - 2):  # 0..3
        assert phases[i].end_hour == phases[i + 1].start_hour
    assert phases[4].end_hour == 24.0
    assert phases[5].start_hour == 24.0
    assert phases[5].end_hour == 24.0


def test_monotonic_clock_progression():
    """Verifică faptul că orele simulate avansează monoton în interiorul fiecărei faze."""
    phases = get_all_phases()

    for phase in phases[:-1]:
        hours = []
        for step in range(11):
            fraction = step / 10.0
            h = phase.start_hour + fraction * (phase.end_hour - phase.start_hour)
            hours.append(h)

        # Verificare monotonie
        for j in range(len(hours) - 1):
            assert hours[j] <= hours[j + 1]


def test_electricity_tariff_profile():
    """Verifică profilul de tarif orar (fix implicit și dinamic opțional)."""
    # 1. Tarif fix (implicit conform cerinței)
    tariff_fix, zone_fix, col_fix = get_electricity_tariff(12.0)
    assert tariff_fix == 1.00
    assert "FIX" in zone_fix.upper()
    assert col_fix == "#38bdf8"

    # 2. Profil dinamic (când fixed_tariff_enabled este False)
    cfg_dynamic = DemoConfig(fixed_tariff_enabled=False)
    tariff_night, _zone_night, _ = get_electricity_tariff(2.0, config=cfg_dynamic)
    tariff_morning, _zone_morning, _ = get_electricity_tariff(8.0, config=cfg_dynamic)
    tariff_noon, _zone_noon, _ = get_electricity_tariff(12.0, config=cfg_dynamic)
    tariff_peak, zone_peak, _ = get_electricity_tariff(16.5, config=cfg_dynamic)
    tariff_evening, _zone_evening, _ = get_electricity_tariff(20.0, config=cfg_dynamic)

    assert tariff_night < tariff_morning
    assert tariff_morning < tariff_noon
    assert tariff_noon < tariff_peak
    assert tariff_peak > tariff_evening
    assert "VÂRF" in zone_peak.upper()


def test_heatwave_target_temperatures():
    """Verifică faptul că la prânz (faza 2) exteriorul atinge 34°C, iar RL rămâne în confort."""
    phases = get_all_phases()
    phase_2 = phases[2]

    # La finalul fazei 2 (ora 15:00), exteriorul ajunge la 34°C
    targets_end = get_simulated_targets(phase_2, fraction_in_phase=1.0, wall_elapsed_in_phase=80.0)
    assert targets_end["temp_ext"] == 34.0

    # Interior RL rămâne în intervalul 21.0 - 24.0°C
    assert 21.0 <= targets_end["temp_int_rl"] <= 24.0
    assert targets_end["temp_int_rl"] == pytest.approx(23.6, abs=0.2)
