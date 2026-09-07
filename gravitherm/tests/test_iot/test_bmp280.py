"""Teste unitare pentru modulul bmp280 (I2C)."""

import struct
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from gravitherm.iot.sensors.bmp280 import (
    BMP280NotFoundError,
    BMP280ReadError,
    BMP280Sensor,
    PressureReading,
    read_pressure,
    read_pressure_bar,
)


def test_pressure_reading_to_sensor_message():
    reading = PressureReading(pressure_bar=2.4567, temperature_c=21.5)
    msg = reading.to_sensor_message()

    assert msg["unit"] == "bar"
    assert msg["value"] == 2.457
    assert "timestamp" in msg
    # Verificam ca timestamp-ul este ISO8601 valid
    parsed_dt = datetime.fromisoformat(msg["timestamp"])
    assert parsed_dt is not None


def test_bmp280_sensor_to_sensor_message_with_value():
    sensor = BMP280Sensor(i2c_address=0x76, bus_id=1)
    msg = sensor.to_sensor_message(pressure_bar=3.14159)

    assert msg["unit"] == "bar"
    assert msg["value"] == 3.142
    assert "timestamp" in msg


def test_bmp280_sensor_to_sensor_message_out_of_bounds():
    sensor = BMP280Sensor(min_pressure_bar=0.0, max_pressure_bar=10.0)
    with pytest.raises(BMP280ReadError, match="limite"):
        sensor.to_sensor_message(pressure_bar=12.5)

    with pytest.raises(BMP280ReadError, match="limite"):
        sensor.to_sensor_message(pressure_bar=-0.5)


def test_read_pressure_bar_with_adafruit_mock():
    # Adafruit BMP280 returneaza presiunea in hPa (1000 hPa = 1 bar)
    mock_device = MagicMock()
    mock_device.pressure = 2500.0  # 2500 hPa = 2.5 bar
    mock_device.temperature = 23.4

    sensor = BMP280Sensor(i2c_address=0x76, device=mock_device, backend="adafruit")
    p_bar = sensor.read_pressure_bar()

    assert p_bar == 2.5
    reading = sensor.read_pressure()
    assert reading.pressure_bar == 2.5
    assert reading.temperature_c == 23.4


def test_read_pressure_bar_with_smbus_mock():
    # Simulam un dispozitiv smbus2 cu calibrare si registre valide
    mock_bus = MagicMock()
    # 0xD0: chip_id BMP280
    mock_bus.read_byte_data.return_value = 0x58

    # Coeficienti de calibrare tipici BMP280 (24 octeti)
    # dig_T1, dig_T2, dig_T3, dig_P1..P9
    calib_bytes = struct.pack(
        "<HhhHhhhhhhhh",
        27504,
        26435,
        -1000,
        36477,
        -10685,
        3024,
        2855,
        140,
        -7,
        15500,
        -14600,
        6000,
    )

    # Date brute pentru T ~ 20C si P ~ 101325 Pa (1.013 bar)
    # raw_p = 345000 (0x0543A0), raw_t = 515000 (0x07DBE0)
    # raw_p -> msb=0x05, lsb=0x43, xlsb=0xA0
    # raw_t -> msb=0x07, lsb=0xDB, xlsb=0xE0
    data_bytes = bytes([0x05, 0x43, 0xA0, 0x07, 0xDB, 0xE0])

    def mock_read_block(addr, reg, length):
        if reg == 0x88:
            return list(calib_bytes)
        if reg == 0xF7:
            return list(data_bytes)
        return [0] * length

    mock_bus.read_i2c_block_data.side_effect = mock_read_block

    sensor = BMP280Sensor(i2c_address=0x76, device=mock_bus, backend="smbus2")
    reading = sensor.read_pressure()

    assert 0.5 <= reading.pressure_bar <= 2.0
    assert reading.temperature_c is not None


def test_smbus_wrong_chip_id_raises_not_found():
    mock_bus = MagicMock()
    mock_bus.read_byte_data.return_value = 0x00  # Chip ID invalid

    sensor = BMP280Sensor(i2c_address=0x76, device=mock_bus, backend="smbus2")
    with pytest.raises(BMP280NotFoundError, match="chip ID"):
        sensor.read_pressure(max_retries=1)


def test_retry_mechanism_recovers_after_transient_oserror():
    mock_device = MagicMock()
    calls = 0

    def mock_pressure():
        nonlocal calls
        calls += 1
        if calls < 3:
            raise OSError("I2C bus transmission error (Errno 121)")
        return 3000.0  # 3000 hPa = 3.0 bar

    type(mock_device).pressure = property(lambda self: mock_pressure())
    mock_device.temperature = 20.0

    sensor = BMP280Sensor(i2c_address=0x76, device=mock_device, backend="adafruit")
    val = sensor.read_pressure_bar(max_retries=3, retry_delay_s=0.01)

    assert val == 3.0
    assert calls == 3


def test_retry_exhausted_raises_bmp280_read_error():
    mock_device = MagicMock()
    type(mock_device).pressure = property(lambda self: (_ for _ in ()).throw(OSError("I2C failure")))

    sensor = BMP280Sensor(i2c_address=0x76, device=mock_device, backend="adafruit")
    with pytest.raises(BMP280ReadError, match="dupa 3 incercari"):
        sensor.read_pressure_bar(max_retries=3, retry_delay_s=0.01)


def test_physical_limits_check_negative_raises():
    mock_device = MagicMock()
    mock_device.pressure = -100.0  # Valoare negativa aberanta
    mock_device.temperature = 22.0

    sensor = BMP280Sensor(i2c_address=0x76, device=mock_device, backend="adafruit")
    with pytest.raises(BMP280ReadError, match="limitelor"):
        sensor.read_pressure_bar(max_retries=1)


def test_physical_limits_check_high_pressure_raises():
    mock_device = MagicMock()
    mock_device.pressure = 15000.0  # 15.0 bar (> 10.0 bar limita default)
    mock_device.temperature = 22.0

    sensor = BMP280Sensor(i2c_address=0x76, device=mock_device, backend="adafruit")
    with pytest.raises(BMP280ReadError, match="limitelor"):
        sensor.read_pressure_bar(max_retries=1)


def test_custom_physical_limits():
    mock_device = MagicMock()
    mock_device.pressure = 3500.0  # 3.5 bar
    mock_device.temperature = 22.0

    sensor = BMP280Sensor(
        i2c_address=0x76,
        min_pressure_bar=1.0,
        max_pressure_bar=3.0,
        device=mock_device,
        backend="adafruit",
    )
    with pytest.raises(BMP280ReadError, match="limitelor"):
        sensor.read_pressure_bar(max_retries=1)


def test_custom_i2c_address_and_bus():
    sensor = BMP280Sensor(i2c_address=0x77, bus_id=2)
    assert sensor.i2c_address == 0x77
    assert sensor.bus_id == 2


def test_missing_libraries_raises_bmp280_read_error():
    sensor = BMP280Sensor(i2c_address=0x76, bus_id=1)
    with (
        patch("gravitherm.iot.sensors.bmp280.HAS_ADAFRUIT_BMP280", False),
        patch("gravitherm.iot.sensors.bmp280.HAS_SMBUS2", False),
        pytest.raises(BMP280ReadError, match="Nicio librarie I2C"),
    ):
        sensor.read_pressure_bar(max_retries=1)


def test_module_functions_read_pressure():
    mock_device = MagicMock()
    mock_device.pressure = 1800.0
    mock_device.temperature = 24.5

    with patch("gravitherm.iot.sensors.bmp280.BMP280Sensor") as mock_sensor_cls:
        mock_instance = MagicMock()
        mock_instance.read_pressure.return_value = PressureReading(pressure_bar=1.8, temperature_c=24.5)
        mock_instance.read_pressure_bar.return_value = 1.8
        mock_sensor_cls.return_value = mock_instance

        reading = read_pressure(i2c_address=0x77, bus_id=2)
        assert reading.pressure_bar == 1.8
        assert reading.temperature_c == 24.5
        mock_sensor_cls.assert_called_with(i2c_address=0x77, bus_id=2)

        p_bar = read_pressure_bar(i2c_address=0x77, bus_id=2)
        assert p_bar == 1.8
