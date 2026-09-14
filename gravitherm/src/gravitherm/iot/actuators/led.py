"""Controler LED RGB - indicator vizual de stare al sistemului GraviTherm."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any

try:
    from gpiozero import RGBLED  # type: ignore[import-untyped]

    GPIOZERO_AVAILABLE = True
except (ImportError, RuntimeError):
    GPIOZERO_AVAILABLE = False


class LedState(Enum):
    """Stări predefinite pentru indicatorul LED RGB al sistemului."""

    GREEN = "green"  # Rulare normală / Optimizare RL activă
    BLUE = "blue"  # Stare inactivă / Standby / Pre-răcire
    RED = "red"  # Eroare critică / Safe Mode
    OFF = "off"  # Indicator dezactivat


_COLOR_MAP: dict[LedState, tuple[float, float, float]] = {
    LedState.GREEN: (0.0, 1.0, 0.0),
    LedState.BLUE: (0.0, 0.0, 1.0),
    LedState.RED: (1.0, 0.0, 0.0),
    LedState.OFF: (0.0, 0.0, 0.0),
}


class _MockRGBLED:
    """Mock pentru gpiozero.RGBLED când rulăm pe un mediu fără pini GPIO fizici."""

    def __init__(
        self,
        red: int,
        green: int,
        blue: int,
        active_high: bool = True,
        initial_value: tuple[float, float, float] = (0.0, 0.0, 0.0),
    ) -> None:
        self.red_pin = red
        self.green_pin = green
        self.blue_pin = blue
        self.active_high = active_high
        self.value = initial_value
        self.is_blinking = False

    def blink(
        self,
        on_time: float = 1.0,
        off_time: float = 1.0,
        on_color: tuple[float, float, float] = (1.0, 0.0, 0.0),
        off_color: tuple[float, float, float] = (0.0, 0.0, 0.0),
        n: int | None = None,
        background: bool = True,
    ) -> None:
        self.value = on_color
        self.is_blinking = True

    def off(self) -> None:
        self.value = (0.0, 0.0, 0.0)
        self.is_blinking = False

    def close(self) -> None:
        self.off()


class RGBLEDController:
    """Controler hardware pentru LED-ul RGB indicator al stării GraviTherm.

    Gestionează stările vizuale (Verde, Albastru, Roșu, Off) și semnalizarea
    intermitentă (blink) pentru alerte sau erori critice.
    """

    def __init__(
        self,
        red_pin: int = 23,
        green_pin: int = 24,
        blue_pin: int = 25,
        active_high: bool = True,
    ) -> None:
        """Inițializează pinii GPIO pentru canalele R, G, B ale LED-ului.

        Parameters
        ----------
        red_pin : int
            Pinul GPIO pentru canalul Roșu.
        green_pin : int
            Pinul GPIO pentru canalul Verde.
        blue_pin : int
            Pinul GPIO pentru canalul Albastru.
        active_high : int
            Specifică dacă LED-ul este catod comun (True) sau anod comun (False).
        """
        self.red_pin = red_pin
        self.green_pin = green_pin
        self.blue_pin = blue_pin

        self._state: LedState = LedState.OFF
        self._color: tuple[float, float, float] = (0.0, 0.0, 0.0)
        self._is_blinking: bool = False

        if GPIOZERO_AVAILABLE:
            self._device = RGBLED(
                red=red_pin,
                green=green_pin,
                blue=blue_pin,
                active_high=active_high,
                initial_value=(0.0, 0.0, 0.0),
            )
        else:
            self._device = _MockRGBLED(
                red=red_pin,
                green=green_pin,
                blue=blue_pin,
                active_high=active_high,
                initial_value=(0.0, 0.0, 0.0),
            )

        self.off()

    @property
    def state(self) -> LedState:
        """Starea curentă a LED-ului (LedState)."""
        return self._state

    @property
    def color(self) -> tuple[float, float, float]:
        """Culoarea curentă RGB a LED-ului sub formă de tuplu (R, G, B) în intervalul [0.0, 1.0]."""
        return self._color

    @property
    def is_blinking(self) -> bool:
        """Indică dacă LED-ul este în modul de semnalizare intermitentă."""
        return self._is_blinking

    def set_state(self, state: LedState | str) -> None:
        """Setează starea LED-ului folosind stările predefinite (VERDE, ALBASTRU, ROȘU, OFF).

        Parameters
        ----------
        state : LedState | str
            Starea dorită (obiect LedState sau valoarea sa string "green", "blue", "red", "off").
        """
        if isinstance(state, str):
            try:
                state_enum = LedState(state.lower())
            except ValueError:
                state_enum = LedState.OFF
        else:
            state_enum = state

        self._state = state_enum
        self._color = _COLOR_MAP.get(state_enum, (0.0, 0.0, 0.0))
        self._is_blinking = False

        if state_enum == LedState.OFF:
            self._device.off()
        else:
            self._device.value = self._color

    def set_color(self, red: float, green: float, blue: float) -> None:
        """Setează o culoare personalizată RGB pentru LED.

        Parameters
        ----------
        red : float
            Intensitate canal roșu (0.0 - 1.0).
        green : float
            Intensitate canal verde (0.0 - 1.0).
        blue : float
            Intensitate canal albastru (0.0 - 1.0).
        """
        r = max(0.0, min(1.0, float(red)))
        g = max(0.0, min(1.0, float(green)))
        b = max(0.0, min(1.0, float(blue)))

        self._color = (r, g, b)
        self._is_blinking = False

        if (r, g, b) == (0.0, 0.0, 0.0):
            self._state = LedState.OFF
            self._device.off()
        else:
            self._device.value = (r, g, b)

    def blink(
        self,
        state: LedState = LedState.RED,
        on_time: float = 0.5,
        off_time: float = 0.5,
        n: int | None = None,
    ) -> None:
        """Semnalizează intermitent (blink) LED-ul cu o culoare dată, util pentru alerte/erori.

        Parameters
        ----------
        state : LedState
            Starea/culoarea pentru semnalul intermitent (implicit ROȘU).
        on_time : float
            Durata în secunde pentru starea aprinsă (default 0.5s).
        off_time : float
            Durata în secunde pentru starea stinsă (default 0.5s).
        n : int | None
            Numărul de cicluri de clipire (None pentru clipire continuă).
        """
        self._state = state
        self._color = _COLOR_MAP.get(state, (1.0, 0.0, 0.0))
        self._is_blinking = True

        if hasattr(self._device, "blink"):
            try:
                self._device.blink(
                    on_time=on_time,
                    off_time=off_time,
                    on_color=self._color,
                    off_color=(0.0, 0.0, 0.0),
                    n=n,
                    background=True,
                )
            except TypeError:
                self._device.value = self._color

    def off(self) -> None:
        """Stinge LED-ul RGB."""
        self.set_state(LedState.OFF)

    def to_telemetry_message(self) -> dict[str, Any]:
        """Generează mesajul de telemetrie conform contractului din interfaces.py.

        Returns
        -------
        dict[str, Any]
            Dicționar cu timestamp UTC ISO8601, starea LED-ului, valorile RGB și unitatea.
        """
        return {
            "timestamp": datetime.now(UTC).isoformat(),
            "state": self._state.value,
            "color": list(self._color),
            "value": 1.0 if self._state != LedState.OFF else 0.0,
            "unit": "rgb",
        }

    def close(self) -> None:
        """Eliberează resursele pini GPIO ai LED-ului."""
        self.off()
        self._device.close()


_DEFAULT_LED_CONTROLLER: RGBLEDController | None = None


def set_led(state: LedState | str) -> None:
    """Funcție utilitară globală pentru setarea rapidă a stării LED-ului.

    Parameters
    ----------
    state : LedState | str
        Starea LED-ului (GREEN, BLUE, RED, OFF sau string corespunzător).
    """
    global _DEFAULT_LED_CONTROLLER
    if _DEFAULT_LED_CONTROLLER is None:
        _DEFAULT_LED_CONTROLLER = RGBLEDController()
    _DEFAULT_LED_CONTROLLER.set_state(state)
