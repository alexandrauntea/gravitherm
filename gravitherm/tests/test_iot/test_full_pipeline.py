"""Teste unitare pentru modulul IoT (mqtt_client, influx_writer, rpi_main, senzori)."""

from gravitherm.interfaces import Action, Observation
from gravitherm.iot.influx_writer import InfluxDBWriter, write_point
from gravitherm.iot.mqtt_client import GraviThermMQTTClient, publish_reading
from gravitherm.iot.rpi_main import EnergyAwarePolicyStub, check_sensor_safety
from gravitherm.iot.sensors import bmp280, ds18b20


def test_sensor_drivers_fallback():
    ds_readings = ds18b20.read_all_sensors()
    assert isinstance(ds_readings, list)
    assert len(ds_readings) >= 1
    assert isinstance(ds_readings[0].temperature_c, float)

    bmp_reading = bmp280.read_pressure()
    assert isinstance(bmp_reading.pressure_bar, float)
    assert isinstance(bmp_reading.temperature_c, float)


def test_mqtt_client_formatting_and_publish():
    client = GraviThermMQTTClient(client_id="test_client")
    client.connect()

    # Publicare măsurători
    client.publish_sensor_reading("temp1", 22.5, "C")
    client.publish_sensor_reading("pressure", 1.013, "bar")
    client.publish_actuator_state(
        "pump", {"timestamp": "2026-09-14T12:00:00Z", "pump_on": True, "value": 100.0, "unit": "pct"}
    )

    publish_reading(client._client, "temp2", 23.0, "C")
    client.disconnect()


def test_influx_writer_point_creation():
    writer = InfluxDBWriter()
    res = writer.write_point(
        measurement="test_measurement",
        fields={"value": 25.4, "status": 1.0},
        tags={"location": "lab"},
    )
    assert isinstance(res, bool)
    writer.close()

    write_point("test_global", 12.3)


def test_rpi_main_safety_check_and_stub():
    assert check_sensor_safety(utl_temp_c=22.5, pressure_bar=1.013) is True
    assert check_sensor_safety(utl_temp_c=99.0, pressure_bar=1.013) is False
    assert check_sensor_safety(utl_temp_c=-10.0, pressure_bar=1.013) is False
    assert check_sensor_safety(utl_temp_c=22.5, pressure_bar=15.0) is False

    stub = EnergyAwarePolicyStub()
    obs = Observation(
        utl_temperature_c=23.0,
        pper_pressure_bar=1.0,
        pper_power_w=20.0,
        hour_of_day=12.0,
        energy_price=0.5,
        hvac_load_w=1500.0,
    )
    action = stub.act(obs)
    assert isinstance(action, Action)
    assert isinstance(action.pump_on, bool)
