"""Teste unitare pentru driverele de actuatoare hardware (pump.py și led.py)."""

from gravitherm.interfaces import Action
from gravitherm.iot.actuators.led import LedState, RGBLEDController, set_led
from gravitherm.iot.actuators.pump import PumpController


def test_pump_controller_initialization_and_safety():
    pump = PumpController()
    assert pump.is_on is False
    assert pump.speed_pct == 0.0

    msg = pump.to_telemetry_message()
    assert "timestamp" in msg
    assert msg["pump_on"] is False
    assert msg["pump_speed_pct"] == 0.0
    assert msg["unit"] == "pct"
    pump.close()


def test_pump_controller_turn_on_and_off():
    pump = PumpController()
    pump.turn_on(75.0)
    assert pump.is_on is True
    assert pump.speed_pct == 75.0

    msg = pump.to_telemetry_message()
    assert msg["pump_on"] is True
    assert msg["pump_speed_pct"] == 75.0
    assert msg["value"] == 75.0

    pump.turn_off()
    assert pump.is_on is False
    assert pump.speed_pct == 0.0
    pump.close()


def test_pump_controller_apply_action():
    pump = PumpController()

    action_on = Action(pump_on=True, pump_speed_pct=50.0)
    pump.apply(action_on)
    assert pump.is_on is True
    assert pump.speed_pct == 50.0

    action_off = Action(pump_on=False, pump_speed_pct=0.0)
    pump.apply(action_off)
    assert pump.is_on is False
    assert pump.speed_pct == 0.0

    pump.close()


def test_pump_controller_stop():
    pump = PumpController()
    pump.turn_on(100.0)
    assert pump.is_on is True
    pump.stop()
    assert pump.is_on is False
    assert pump.speed_pct == 0.0
    pump.close()


def test_rgb_led_controller_states():
    led = RGBLEDController()
    assert led.state == LedState.OFF
    assert led.color == (0.0, 0.0, 0.0)

    led.set_state(LedState.GREEN)
    assert led.state == LedState.GREEN
    assert led.color == (0.0, 1.0, 0.0)

    led.set_state(LedState.BLUE)
    assert led.state == LedState.BLUE
    assert led.color == (0.0, 0.0, 1.0)

    led.set_state(LedState.RED)
    assert led.state == LedState.RED
    assert led.color == (1.0, 0.0, 0.0)

    led.off()
    assert led.state == LedState.OFF
    assert led.color == (0.0, 0.0, 0.0)
    led.close()


def test_rgb_led_controller_string_state_and_telemetry():
    led = RGBLEDController()
    led.set_state("blue")
    assert led.state == LedState.BLUE

    msg = led.to_telemetry_message()
    assert "timestamp" in msg
    assert msg["state"] == "blue"
    assert msg["color"] == [0.0, 0.0, 1.0]
    assert msg["unit"] == "rgb"

    led.close()


def test_rgb_led_controller_blink_and_set_led():
    led = RGBLEDController()
    led.blink(LedState.RED)
    assert led.is_blinking is True
    assert led.state == LedState.RED
    led.off()
    assert led.is_blinking is False

    set_led(LedState.GREEN)
    led.close()


def test_peltier_controller_lifecycle_and_telemetry():
    from gravitherm.iot.actuators.peltier import PeltierController

    peltier = PeltierController(pin=25)
    assert peltier.is_on is False

    peltier.turn_on()
    assert peltier.is_on is True

    msg = peltier.to_telemetry_message()
    assert "timestamp" in msg
    assert msg["peltier_on"] is True
    assert msg["value"] == 1.0
    assert msg["unit"] == "bool"

    peltier.turn_off()
    assert peltier.is_on is False

    peltier.apply(True)
    assert peltier.is_on is True

    peltier.stop()
    assert peltier.is_on is False
    peltier.close()
