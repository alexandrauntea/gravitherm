"""Control LED RGB - indicator vizual al deciziei agentului.

Codificare: verde = recirculare activa, rosu = blocare, albastru = pre-racire.
"""

from enum import Enum


class LedState(Enum):
    GREEN = "green"
    RED = "red"
    BLUE = "blue"


def set_led(state: LedState) -> None:
    """TODO(Andreea): implementati cu gpiozero.RGBLED."""
    raise NotImplementedError("De implementat pe Raspberry Pi cu hardware conectat.")
