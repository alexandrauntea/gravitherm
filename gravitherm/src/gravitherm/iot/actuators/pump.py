"""Controler pentru pompa DC 12V prin driverul hidraulic L298N."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from gravitherm.config import GPIO_PUMP_ENA, GPIO_PUMP_IN1, GPIO_PUMP_IN2
from gravitherm.interfaces import Action

logger = logging.getLogger(__name__)

try:
    from gpiozero import DigitalOutputDevice, PWMOutputDevice  # type: ignore[import-untyped]

    GPIOZERO_AVAILABLE = True
except (ImportError, RuntimeError):
    GPIOZERO_AVAILABLE = False


class _MockPWMOutputDevice:
    """Mock pentru PWMOutputDevice c?nd gpiozero nu este disponibil pe mediul local."""

    def __init__(self, pin: int, initial_value: float = 0.0) -> None:
        self.pin = pin
        self.value = initial_value

    def close(self) -> None:
        self.value = 0.0


class _MockDigitalOutputDevice:
    """Mock pentru DigitalOutputDevice c?nd gpiozero nu este disponibil pe mediul local."""

    def __init__(self, pin: int, initial_value: bool = False) -> None:
        self.pin = pin
        self.value = initial_value

    def on(self) -> None:
        self.value = True

    def off(self) -> None:
        self.value = False

    def close(self) -> None:
        self.value = False


class PumpController:
    """Controler hardware pentru pompa de circula?ie UTL ac?ionat? de un driver L298N.

    Permite controlul st?rii (ON/OFF) ?i ajustarea vitezei prin semnal PWM (dac? pin_pwm este configurat).
    Dac? pin_pwm este None (jumper ENA montat), pompa func?ioneaz? la vitez? fix? 100% c?nd este ON.
    Con?ine mecanisme de protec?ie (safe initialization, stop de urgen??) ?i
    generare de telemetrie conform contractului din interfaces.py.
    """

    def __init__(
        self,
        pin_pwm: int | None = GPIO_PUMP_ENA,
        pin_in1: int = GPIO_PUMP_IN1,
        pin_in2: int = GPIO_PUMP_IN2,
    ) -> None:
        """Ini?ializeaz? pinii GPIO ai driverului L298N ?n stare oprit? (safe default).

        Parameters
        ----------
        pin_pwm : int | None
            Pinul GPIO conectat la intrarea Enable (ENA) pentru semnal PWM.
            Dac? este None, se consider? c? jumper-ul fizic ENA este montat (vitez? fix?).
        pin_in1 : int
            Pinul GPIO conectat la intrarea de direc?ie IN1 (implicit GPIO23).
        pin_in2 : int
            Pinul GPIO conectat la intrarea de direc?ie IN2 (implicit GPIO24).
        """
        self.pin_pwm = pin_pwm
        self.pin_in1 = pin_in1
        self.pin_in2 = pin_in2

        self._is_on: bool = False
        self._speed_pct: float = 0.0

        if GPIOZERO_AVAILABLE:
            try:
                self._device_pwm = (
                    PWMOutputDevice(pin_pwm, initial_value=0.0)
                    if pin_pwm is not None
                    else None
                )
                self._device_in1 = DigitalOutputDevice(pin_in1, initial_value=False)
                self._device_in2 = DigitalOutputDevice(pin_in2, initial_value=False)
            except (OSError, RuntimeError, AttributeError) as err:
                logger.warning(
                    "Eroare ini?ializare pini hardware gpiozero: %s. Se folose?te Mock.",
                    err,
                )
                self._device_pwm = (
                    _MockPWMOutputDevice(pin_pwm, initial_value=0.0)
                    if pin_pwm is not None
                    else None
                )
                self._device_in1 = _MockDigitalOutputDevice(pin_in1, initial_value=False)
                self._device_in2 = _MockDigitalOutputDevice(pin_in2, initial_value=False)
        else:
            self._device_pwm = (
                _MockPWMOutputDevice(pin_pwm, initial_value=0.0)
                if pin_pwm is not None
                else None
            )
            self._device_in1 = _MockDigitalOutputDevice(pin_in1, initial_value=False)
            self._device_in2 = _MockDigitalOutputDevice(pin_in2, initial_value=False)

        self.stop()

    @property
    def is_on(self) -> bool:
        """Indic? dac? pompa este activ?."""
        return self._is_on

    @property
    def speed_pct(self) -> float:
        """Nivelul curent de vitez? PWM al pompei ?n procente (0.0 - 100.0%)."""
        return self._speed_pct

    def turn_on(self, speed_pct: float = 100.0) -> None:
        """Porne?te pompa la viteza specificat?.

        Parameters
        ----------
        speed_pct : float
            Nivelul de vitez? PWM (0.0 p?n? la 100.0%).
        """
        clamped_speed = max(0.0, min(100.0, float(speed_pct)))
        if clamped_speed <= 0.0:
            self.turn_off()
            return

        self._is_on = True
        self._speed_pct = clamped_speed

        # Seteaz? direc?ia de rota?ie ?nainte (IN1=HIGH, IN2=LOW)
        self._device_in1.on()
        self._device_in2.off()
        if self._device_pwm is not None:
            self._device_pwm.value = clamped_speed / 100.0

    def turn_off(self) -> None:
        """Opre?te pompa ?i reseteaz? semnalul la 0."""
        self._is_on = False
        self._speed_pct = 0.0

        if self._device_pwm is not None:
            self._device_pwm.value = 0.0
        self._device_in1.off()
        self._device_in2.off()

    def set_speed(self, speed_pct: float) -> None:
        """Seteaz? nivelul vitezei pompei.

        Parameters
        ----------
        speed_pct : float
            Procentajul vitezei PWM (0.0 - 100.0%).
        """
        if speed_pct > 0.0:
            self.turn_on(speed_pct)
        else:
            self.turn_off()

    def apply(self, action: Action) -> None:
        """Aplic? decizia agentului asupra pompei fizice sau simulate.

        Parameters
        ----------
        action : Action
            Obiectul Action care specific? starea `pump_on` ?i viteza `pump_speed_pct`.
        """
        if action.pump_on:
            speed = action.pump_speed_pct if action.pump_speed_pct > 0.0 else 100.0
            self.turn_on(speed)
        else:
            self.turn_off()

    def stop(self) -> None:
        """Metod? de siguran??: opre?te imediat pompa ?i dezactiveaz? pinii GPIO."""
        self.turn_off()

    def to_telemetry_message(self) -> dict[str, Any]:
        """Genereaz? mesajul de telemetrie conform formatului specificat ?n interfaces.py.

        Returns
        -------
        dict[str, Any]
            Dic?ionar cu timestamp UTC ISO8601, starea pompei, nivelul PWM ?i unitatea.
        """
        return {
            "timestamp": datetime.now(UTC).isoformat(),
            "pump_on": self._is_on,
            "pump_speed_pct": self._speed_pct,
            "value": float(self._speed_pct if self._is_on else 0.0),
            "unit": "pct",
        }

    def close(self) -> None:
        """Elibereaz? resursele de pini GPIO."""
        self.stop()
        if self._device_pwm is not None:
            self._device_pwm.close()
        self._device_in1.close()
        self._device_in2.close()
