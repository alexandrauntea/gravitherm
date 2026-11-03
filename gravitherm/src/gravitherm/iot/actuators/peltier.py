"""Controler pentru modulul termoelectric Peltier TEC1-12706 prin MOSFET/Releu."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from gravitherm.config import GPIO_PELTIER

logger = logging.getLogger(__name__)

try:
    from gpiozero import DigitalOutputDevice  # type: ignore[import-untyped]

    GPIOZERO_AVAILABLE = True
except (ImportError, RuntimeError):
    GPIOZERO_AVAILABLE = False


class _MockDigitalOutputDevice:
    """Mock pentru DigitalOutputDevice c?nd gpiozero nu este disponibil."""

    def __init__(self, pin: int, active_high: bool = True, initial_value: bool = False) -> None:
        self.pin = pin
        self.active_high = active_high
        self.value = initial_value

    def on(self) -> None:
        self.value = True

    def off(self) -> None:
        self.value = False

    def close(self) -> None:
        self.value = False


class PeltierController:
    """Controler hardware pentru modulul Peltier TEC1-12706 ac?ionat printr-un tranzistor MOSFET logic-level.

    Include mecanisme de protec?ie la ini?ializare (stare oprit? implicit?),
    oprire de urgen?? ?i generare de telemetrie pentru monitorizare/MQTT.
    """

    def __init__(
        self,
        pin: int = GPIO_PELTIER,
        active_high: bool = True,
    ) -> None:
        """Ini?ializeaz? pinul GPIO pentru comanda Peltier ?n stare oprit? (safe default).

        Parameters
        ----------
        pin : int
            Pinul GPIO conectat la poarta MOSFET-ului (implicit GPIO25).
        active_high : bool
            True pentru MOSFET Logic-Level N-Channel (1 = ON, 0 = OFF).
        """
        self.pin = pin
        self.active_high = active_high
        self._is_on: bool = False

        if GPIOZERO_AVAILABLE:
            try:
                self._device = DigitalOutputDevice(
                    pin,
                    active_high=active_high,
                    initial_value=False,
                )
            except (OSError, RuntimeError, AttributeError) as err:
                logger.warning(
                    "Eroare ini?ializare pin Peltier gpiozero (GPIO%d): %s. Se folose?te Mock.",
                    pin,
                    err,
                )
                self._device = _MockDigitalOutputDevice(
                    pin,
                    active_high=active_high,
                    initial_value=False,
                )
        else:
            self._device = _MockDigitalOutputDevice(
                pin,
                active_high=active_high,
                initial_value=False,
            )

        self.stop()

    @property
    def is_on(self) -> bool:
        """Indic? dac? elementul Peltier este activat."""
        return self._is_on

    def turn_on(self) -> None:
        """Activeaz? alimentarea elementului Peltier."""
        self._is_on = True
        self._device.on()
        logger.debug("Peltier ACTIVAT pe GPIO%d", self.pin)

    def turn_off(self) -> None:
        """Dezactiveaz? alimentarea elementului Peltier."""
        self._is_on = False
        self._device.off()
        logger.debug("Peltier DEZACTIVAT pe GPIO%d", self.pin)

    def apply(self, turn_on: bool) -> None:
        """Aplic? comanda logic? ON/OFF."""
        if turn_on:
            self.turn_on()
        else:
            self.turn_off()

    def stop(self) -> None:
        """Metod? de siguran??: opre?te imediat modulul Peltier."""
        self.turn_off()

    def to_telemetry_message(self) -> dict[str, Any]:
        """Genereaz? mesajul de telemetrie conform conven?iei din interfaces.py."""
        return {
            "timestamp": datetime.now(UTC).isoformat(),
            "peltier_on": self._is_on,
            "value": 1.0 if self._is_on else 0.0,
            "unit": "bool",
        }

    def close(self) -> None:
        """Opre?te modulul ?i elibereaz? resursa GPIO."""
        self.stop()
        self._device.close()
