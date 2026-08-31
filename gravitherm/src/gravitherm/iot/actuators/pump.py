"""Control pompa DC 12V prin driver L298N."""

from gravitherm.interfaces import Action


class PumpController:
    def __init__(self, pin: int = 17):
        self.pin = pin
        # TODO(Andreea): initializati gpiozero.PWMOutputDevice(pin) sau echivalent.

    def apply(self, action: Action) -> None:
        """Aplica decizia agentului asupra pompei fizice.

        TODO(Andreea): implementati cu gpiozero, ex:
            self.device.value = action.pump_speed_pct / 100 if action.pump_on else 0
        """
        raise NotImplementedError("De implementat pe Raspberry Pi cu hardware conectat.")
