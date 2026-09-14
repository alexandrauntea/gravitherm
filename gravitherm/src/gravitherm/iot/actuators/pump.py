"""Controler pentru pompa DC 12V prin driverul hidraulic L298N."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from gravitherm.interfaces import Action

try:
    from gpiozero import DigitalOutputDevice, PWMOutputDevice  # type: ignore[import-untyped]

    GPIOZERO_AVAILABLE = True
except (ImportError, RuntimeError):
    GPIOZERO_AVAILABLE = False


class _MockPWMOutputDevice:
    """Mock pentru PWMOutputDevice când gpiozero nu este disponibil pe mediul local."""

    def __init__(self, pin: int, initial_value: float = 0.0) -> None:
        self.pin = pin
        self.value = initial_value

    def close(self) -> None:
        self.value = 0.0


class _MockDigitalOutputDevice:
    """Mock pentru DigitalOutputDevice când gpiozero nu este disponibil pe mediul local."""

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
    """Controler hardware pentru pompa de circulație UTL acționată de un driver L298N.

    Permite controlul stării (ON/OFF) și ajustarea vitezei prin semnal PWM.
    Conține mecanisme de protecție (safe initialization, stop de urgență) și
    generare de telemetrie conform contractului din interfaces.py.
    """

    def __init__(
        self,
        pin_pwm: int = 17,
        pin_in1: int = 27,
        pin_in2: int = 22,
    ) -> None:
        """Inițializează pini GPIO ai driverului L298N în stare oprită (safe default).

        Parameters
        ----------
        pin_pwm : int
            Pinul GPIO conectat la intrarea Enable (ENA) pentru semnal PWM.
        pin_in1 : int
            Pinul GPIO conectat la intrarea de direcție IN1.
        pin_in2 : int
            Pinul GPIO conectat la intrarea de direcție IN2.
        """
        self.pin_pwm = pin_pwm
        self.pin_in1 = pin_in1
        self.pin_in2 = pin_in2

        self._is_on: bool = False
        self._speed_pct: float = 0.0

        if GPIOZERO_AVAILABLE:
            self._device_pwm = PWMOutputDevice(pin_pwm, initial_value=0.0)
            self._device_in1 = DigitalOutputDevice(pin_in1, initial_value=False)
            self._device_in2 = DigitalOutputDevice(pin_in2, initial_value=False)
        else:
            self._device_pwm = _MockPWMOutputDevice(pin_pwm, initial_value=0.0)
            self._device_in1 = _MockDigitalOutputDevice(pin_in1, initial_value=False)
            self._device_in2 = _MockDigitalOutputDevice(pin_in2, initial_value=False)

        self.stop()

    @property
    def is_on(self) -> bool:
        """Indică dacă pompa este activă."""
        return self._is_on

    @property
    def speed_pct(self) -> float:
        """Nivelul curent de viteză PWM al pompei în procente (0.0 - 100.0%)."""
        return self._speed_pct

    def turn_on(self, speed_pct: float = 100.0) -> None:
        """Pornește pompa la viteza specificată.

        Parameters
        ----------
        speed_pct : float
            Nivelul de viteză PWM (0.0 până la 100.0%).
        """
        clamped_speed = max(0.0, min(100.0, float(speed_pct)))
        if clamped_speed <= 0.0:
            self.turn_off()
            return

        self._is_on = True
        self._speed_pct = clamped_speed

        # Setează direcția de rotație înainte (IN1=HIGH, IN2=LOW)
        self._device_in1.on()
        self._device_in2.off()
        self._device_pwm.value = clamped_speed / 100.0

    def turn_off(self) -> None:
        """Oprește pompa și resetează semnalul PWM la 0."""
        self._is_on = False
        self._speed_pct = 0.0

        self._device_pwm.value = 0.0
        self._device_in1.off()
        self._device_in2.off()

    def set_speed(self, speed_pct: float) -> None:
        """Setează nivelul vitezei pompei.

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
        """Aplică decizia agentului asupra pompei fizice sau simulate.

        Parameters
        ----------
        action : Action
            Obiectul Action care specifică starea `pump_on` și viteza `pump_speed_pct`.
        """
        if action.pump_on:
            speed = action.pump_speed_pct if action.pump_speed_pct > 0.0 else 100.0
            self.turn_on(speed)
        else:
            self.turn_off()

    def stop(self) -> None:
        """Metodă de siguranță: oprește imediat pompa și dezactivează pinii GPIO."""
        self.turn_off()

    def to_telemetry_message(self) -> dict[str, Any]:
        """Generează mesajul de telemetrie conform formatului specificat în interfaces.py.

        Returns
        -------
        dict[str, Any]
            Dicționar cu timestamp UTC ISO8601, starea pompei, nivelul PWM și unitatea.
        """
        return {
            "timestamp": datetime.now(UTC).isoformat(),
            "pump_on": self._is_on,
            "pump_speed_pct": self._speed_pct,
            "value": float(self._speed_pct if self._is_on else 0.0),
            "unit": "pct",
        }

    def close(self) -> None:
        """Eliberează resursele de pini GPIO."""
        self.stop()
        self._device_pwm.close()
        self._device_in1.close()
        self._device_in2.close()
