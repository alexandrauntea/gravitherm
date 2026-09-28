"""Teste unitare pentru modulul ds18b20 (1-Wire)."""

from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from gravitherm.iot.sensors.ds18b20 import (
    DS18B20Sensor,
    SensorNotFoundError,
    SensorReadError,
    TemperatureReading,
    get_available_sensors,
    read_all_sensors,
    read_temperature,
)


def test_temperature_reading_to_sensor_message():
    reading = TemperatureReading(sensor_id="28-000001234567", temperature_c=22.4567)
    msg = reading.to_sensor_message()

    assert msg["unit"] == "celsius"
    assert msg["value"] == 22.457
    assert "timestamp" in msg
    # Verificam ca timestamp-ul este ISO8601 valid
    parsed_dt = datetime.fromisoformat(msg["timestamp"])
    assert parsed_dt is not None


def test_read_sysfs_valid(tmp_path: Path):
    sensor_id = "28-000001111111"
    sensor_dir = tmp_path / sensor_id
    sensor_dir.mkdir(parents=True)
    slave_file = sensor_dir / "w1_slave"
    slave_file.write_text(
        "72 01 4b 46 7f ff 0e 10 57 : crc=57 YES\n" "72 01 4b 46 7f ff 0e 10 57 t=21875\n",
        encoding="utf-8",
    )

    sensor = DS18B20Sensor(sensor_id=sensor_id, w1_path=tmp_path)
    assert sensor.exists() is True
    temp = sensor.read_temperature()
    assert temp == 21.875


def test_read_sysfs_negative_temperature(tmp_path: Path):
    sensor_id = "28-000002222222"
    sensor_dir = tmp_path / sensor_id
    sensor_dir.mkdir(parents=True)
    slave_file = sensor_dir / "w1_slave"
    slave_file.write_text(
        "00 00 00 00 00 00 00 00 00 : crc=00 YES\n" "00 00 00 00 00 00 00 00 00 t=-12500\n",
        encoding="utf-8",
    )

    sensor = DS18B20Sensor(sensor_id=sensor_id, w1_path=tmp_path)
    temp = sensor.read_temperature()
    assert temp == -12.5


def test_read_sensor_not_found(tmp_path: Path):
    sensor = DS18B20Sensor(sensor_id="28-nonexistent", w1_path=tmp_path)
    assert sensor.exists() is False
    with pytest.raises(SensorNotFoundError):
        sensor.read_temperature(max_retries=1)


def test_read_crc_error_exhausted(tmp_path: Path):
    sensor_id = "28-000003333333"
    sensor_dir = tmp_path / sensor_id
    sensor_dir.mkdir(parents=True)
    slave_file = sensor_dir / "w1_slave"
    slave_file.write_text(
        "72 01 4b 46 7f ff 0e 10 57 : crc=57 NO\n" "72 01 4b 46 7f ff 0e 10 57 t=21875\n",
        encoding="utf-8",
    )

    sensor = DS18B20Sensor(sensor_id=sensor_id, w1_path=tmp_path)
    with pytest.raises(SensorReadError, match="CRC"):
        sensor.read_temperature(max_retries=2, retry_delay_s=0.01)


def test_read_power_on_reset_value_85c(tmp_path: Path):
    sensor_id = "28-000004444444"
    sensor_dir = tmp_path / sensor_id
    sensor_dir.mkdir(parents=True)
    slave_file = sensor_dir / "w1_slave"
    slave_file.write_text(
        "72 01 4b 46 7f ff 0e 10 57 : crc=57 YES\n" "72 01 4b 46 7f ff 0e 10 57 t=85000\n",
        encoding="utf-8",
    )

    sensor = DS18B20Sensor(sensor_id=sensor_id, w1_path=tmp_path)
    with pytest.raises(SensorReadError, match="85.0"):
        sensor.read_temperature(max_retries=2, retry_delay_s=0.01)


def test_retry_mechanism_recovers_after_transient_crc_error(tmp_path: Path):
    sensor_id = "28-000005555555"
    sensor_dir = tmp_path / sensor_id
    sensor_dir.mkdir(parents=True)
    slave_file = sensor_dir / "w1_slave"

    calls = 0
    real_read_text = Path.read_text

    def mock_read_text(self, *args, **kwargs):
        nonlocal calls
        if self == slave_file:
            calls += 1
            if calls == 1:
                return "00 : crc=00 NO\n00 t=0\n"
            return "57 : crc=57 YES\n57 t=24500\n"
        return real_read_text(self, *args, **kwargs)

    slave_file.write_text("dummy", encoding="utf-8")
    sensor = DS18B20Sensor(sensor_id=sensor_id, w1_path=tmp_path)

    with patch.object(Path, "read_text", side_effect=mock_read_text, autospec=True):
        temp = sensor.read_temperature(max_retries=3, retry_delay_s=0.01)
        assert temp == 24.5
        assert calls == 2


def test_get_available_sensors(tmp_path: Path):
    (tmp_path / "28-00001").mkdir()
    (tmp_path / "28-00002").mkdir()
    (tmp_path / "w1_bus_master1").mkdir()
    (tmp_path / "10-00003").mkdir()

    sensors = get_available_sensors(w1_path=tmp_path)
    assert sensors == ["28-00001", "28-00002"]


def test_read_all_sensors(tmp_path: Path):
    for sid, t_val in [("28-00001", 18500), ("28-00002", 23250)]:
        sdir = tmp_path / sid
        sdir.mkdir()
        (sdir / "w1_slave").write_text(f"57 : crc=57 YES\n57 t={t_val}\n", encoding="utf-8")

    readings = read_all_sensors(w1_path=tmp_path)
    assert len(readings) == 2
    assert readings[0].sensor_id == "28-00001"
    assert readings[0].temperature_c == 18.5
    assert readings[1].sensor_id == "28-00002"
    assert readings[1].temperature_c == 23.25


def test_read_all_sensors_empty_raises(tmp_path: Path):
    with pytest.raises(SensorNotFoundError):
        read_all_sensors(w1_path=tmp_path)


def test_read_temperature_helper(tmp_path: Path):
    sdir = tmp_path / "28-first"
    sdir.mkdir()
    (sdir / "w1_slave").write_text("57 : crc=57 YES\n57 t=20000\n", encoding="utf-8")

    temp_auto = read_temperature(w1_path=tmp_path)
    assert temp_auto == 20.0

    temp_specific = read_temperature(sensor_id="28-first", w1_path=tmp_path)
    assert temp_specific == 20.0
