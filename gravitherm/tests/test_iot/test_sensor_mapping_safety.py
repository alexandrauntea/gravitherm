"""Teste pentru noua mapare a senzorilor DS18B20, siguranța termică Peltier și contractul ONNX."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from gravitherm.agent.env_adapter import obs_to_array
from gravitherm.config import (
    DS18B20_COLD_SIDE,
    DS18B20_HOT_SIDE,
    DS18B20_RESERVOIR,
    DS18B20_ROLES,
    HOT_SIDE_LIMIT_C,
    HOT_SIDE_WARN_C,
)
from gravitherm.interfaces import Observation
from gravitherm.iot.actuators.peltier import PeltierController
from gravitherm.iot.rpi_main import check_peltier_thermal_safety
from gravitherm.iot.sensors.ds18b20 import (
    read_mapped_temperatures,
    read_sensor_by_role,
)


def test_sensor_roles_mapping_in_config():
    """Validează că config.py conține exact cele 3 roluri definitive ale senzorilor."""
    assert DS18B20_COLD_SIDE == "28-0000006ca69e"
    assert DS18B20_RESERVOIR == "28-0000006e6d0e"
    assert DS18B20_HOT_SIDE == "28-0000006ffba8"

    assert set(DS18B20_ROLES.keys()) == {"cold_side", "reservoir", "hot_side"}
    assert DS18B20_ROLES["cold_side"] == "28-0000006ca69e"
    assert DS18B20_ROLES["reservoir"] == "28-0000006e6d0e"
    assert DS18B20_ROLES["hot_side"] == "28-0000006ffba8"

    # Praguri sigure pentru Peltier TEC1-12706
    assert HOT_SIDE_WARN_C == 50.0
    assert HOT_SIDE_LIMIT_C == 60.0


def test_read_mapped_temperatures_with_sysfs_mock(tmp_path: Path):
    """Verifică asocierea corectă între ID-uri și roluri din sysfs."""
    # Cream fisiere sysfs mock pentru toti cei 3 senzori
    for role, sid, temp_millic in [
        ("reservoir", DS18B20_RESERVOIR, 24125),
        ("cold_side", DS18B20_COLD_SIDE, 13500),
        ("hot_side", DS18B20_HOT_SIDE, 35000),
    ]:
        sdir = tmp_path / sid
        sdir.mkdir(parents=True)
        (sdir / "w1_slave").write_text(f"57 : crc=57 YES\n57 t={temp_millic}\n", encoding="utf-8")

    mapped = read_mapped_temperatures(w1_path=tmp_path)
    assert mapped["reservoir"] == pytest.approx(24.125, rel=1e-3)
    assert mapped["cold_side"] == pytest.approx(13.5, rel=1e-3)
    assert mapped["hot_side"] == pytest.approx(35.0, rel=1e-3)

    # Citire pe rol individual
    assert read_sensor_by_role("reservoir", w1_path=tmp_path) == pytest.approx(24.125, rel=1e-3)
    assert read_sensor_by_role("cold_side", w1_path=tmp_path) == pytest.approx(13.5, rel=1e-3)
    assert read_sensor_by_role("hot_side", w1_path=tmp_path) == pytest.approx(35.0, rel=1e-3)


def test_read_mapped_temperatures_missing_sensor(tmp_path: Path):
    """Dacă un senzor lipsește de pe bus, valoarea lui este None și nu blochează restul."""
    # Doar rezervorul este conectat
    sdir = tmp_path / DS18B20_RESERVOIR
    sdir.mkdir(parents=True)
    (sdir / "w1_slave").write_text("57 : crc=57 YES\n57 t=22000\n", encoding="utf-8")

    mapped = read_mapped_temperatures(w1_path=tmp_path)
    assert mapped["reservoir"] == 22.0
    assert mapped["cold_side"] is None
    assert mapped["hot_side"] is None


def test_peltier_thermal_safety_ok():
    """Temperatura sub 50°C este considerată sigură."""
    safe, msg = check_peltier_thermal_safety(42.5)
    assert safe is True
    assert msg == "OK"


def test_peltier_thermal_safety_critical_cutoff():
    """Temperatura >= 60°C declanșează tăierea forțată a alimentării Peltier."""
    safe, msg = check_peltier_thermal_safety(60.0)
    assert safe is False
    assert "[SAFETY]" in msg
    assert "CRITICĂ" in msg

    safe_over, msg_over = check_peltier_thermal_safety(65.2)
    assert safe_over is False
    assert "[SAFETY]" in msg_over


def test_peltier_thermal_safety_failsafe_on_missing_sensor():
    """Dacă senzorul cald nu poate fi citit (None), se declanșează starea Fail-Safe."""
    safe, msg = check_peltier_thermal_safety(None)
    assert safe is False
    assert "[SAFETY]" in msg
    assert "DECONECTAT" in msg


def test_observation_shape_invariance_for_onnx():
    """Validează că tensorul Observation trimis către modelul ONNX are exact forma (1, 6)."""
    obs = Observation(
        utl_temperature_c=23.4,  # alimentat din rezervor
        pper_pressure_bar=1.15,
        pper_power_w=18.5,
        hour_of_day=14.5,
        energy_price=0.45,
        hvac_load_w=200.0,
    )

    arr = obs_to_array(obs)
    assert arr.shape == (6,)
    assert arr.dtype == np.float32

    # Array-ul cu dimensiunea de batch trimis în onnxruntime session.run()
    batch_arr = np.array([arr], dtype=np.float32)
    assert batch_arr.shape == (1, 6)

    # Verificare că primul element este temperatura din rezervor
    assert batch_arr[0, 0] == pytest.approx(23.4, rel=1e-4)


def test_peltier_controller_shutdown():
    """Verifică decuplarea Peltier prin stop()."""
    controller = PeltierController()
    controller.turn_on()
    assert controller.is_on is True

    controller.stop()
    assert controller.is_on is False

