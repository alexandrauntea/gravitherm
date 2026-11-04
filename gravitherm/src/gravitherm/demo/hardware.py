"""Gestionar hardware pentru demo-ul live GraviTherm.

Asigură comanda sigură a pompei (prin L298N) și a modulului Peltier (prin MOSFET),
cu protecții critice:
- oprire de urgență la SIGINT (Ctrl+C), SIGTERM, atexit și excepții;
- watchdog independent de 3 secunde pentru decuplare la blocarea thread-ului;
- limită termică și de timp (max 5 minute continuu) pentru Peltier;
- protecție împotriva mersului în gol pentru pompă (PUMP_ENABLED);
- suport unificat pentru mod REAL (pe Raspberry Pi) și MOCK (pe laptop).
"""

from __future__ import annotations

import atexit
import logging
import signal
import sys
import threading
import time
from typing import Any

from gravitherm.demo.demo_config import DemoConfig

logger = logging.getLogger("gravitherm.demo.hardware")


class MockPump:
    """Actuator mock pentru pompă pe laptop / fără hardware."""

    def __init__(self) -> None:
        self.is_on: bool = False
        self.speed_pct: float = 0.0

    def turn_on(self, speed_pct: float = 100.0) -> None:
        self.is_on = True
        self.speed_pct = max(0.0, min(100.0, float(speed_pct)))

    def turn_off(self) -> None:
        self.is_on = False
        self.speed_pct = 0.0

    def stop(self) -> None:
        self.turn_off()

    def close(self) -> None:
        self.turn_off()


class MockPeltier:
    """Actuator mock pentru Peltier pe laptop / fără hardware."""

    def __init__(self) -> None:
        self.is_on: bool = False

    def turn_on(self) -> None:
        self.is_on = True

    def turn_off(self) -> None:
        self.is_on = False

    def apply(self, turn_on: bool) -> None:
        self.is_on = bool(turn_on)

    def stop(self) -> None:
        self.turn_off()

    def close(self) -> None:
        self.turn_off()


class HardwareManager:
    """Manager complet de actuatori cu garanție de oprire în siguranță."""

    def __init__(self, config: DemoConfig | None = None, mock_mode: bool = False) -> None:
        self.cfg = config or DemoConfig()
        self.mock_mode = mock_mode
        self._lock = threading.RLock()

        self._pump_enabled: bool = self.cfg.pump_enabled
        self._pump: Any = None
        self._peltier: Any = None

        # Telemetrie și stări de siguranță
        self._pump_state: bool = False
        self._pump_speed_pct: float = 0.0
        self._peltier_state: bool = False

        self._last_heartbeat: float = time.time()
        self._peltier_on_start_time: float | None = None
        self._watchdog_active: bool = True
        self._emergency_stopped: bool = False

        self._init_actuators()
        self._register_safety_handlers()

        # Pornire thread watchdog de siguranță
        self._watchdog_thread = threading.Thread(
            target=self._watchdog_loop,
            name="HardwareSafetyWatchdog",
            daemon=True,
        )
        self._watchdog_thread.start()

    def _init_actuators(self) -> None:
        """Inițializează controlerele hardware sau mock-urile corespunzătoare."""
        if self.mock_mode:
            logger.info("[Hardware] Mod MOCK activat explicit: se folosesc actuatori virtuali.")
            self._pump = MockPump()
            self._peltier = MockPeltier()
            return

        # Încercare încărcare drivere reale
        try:
            from gravitherm.iot.actuators.peltier import PeltierController
            from gravitherm.iot.actuators.pump import PumpController

            logger.info(
                "[Hardware] Inițializare hardware real: Pompă IN1=%s IN2=%s ENA=%s | Peltier GPIO=%s",
                self.cfg.gpio_pump_in1,
                self.cfg.gpio_pump_in2,
                self.cfg.gpio_pump_ena,
                self.cfg.gpio_peltier,
            )
            self._pump = PumpController(
                pin_pwm=self.cfg.gpio_pump_ena,
                pin_in1=self.cfg.gpio_pump_in1,
                pin_in2=self.cfg.gpio_pump_in2,
            )
            self._peltier = PeltierController(pin=self.cfg.gpio_peltier)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "[Hardware] Nu s-au putut inițializa driverele fizice (%s). Se comută automat pe MOCK.",
                exc,
            )
            self.mock_mode = True
            self._pump = MockPump()
            self._peltier = MockPeltier()

        # Stare inițială garantat oprită
        self.stop_all()

    def _register_safety_handlers(self) -> None:
        """Înregistrează hook-urile de siguranță la nivel de sistem."""
        # atexit la închiderea procesului
        atexit.register(self.emergency_stop)

        # Semnale OS (pe thread-ul principal dacă este posibil)
        if threading.current_thread() is threading.main_thread():
            try:
                signal.signal(signal.SIGINT, self._handle_os_signal)
                signal.signal(signal.SIGTERM, self._handle_os_signal)
            except (ValueError, AttributeError) as exc:
                logger.debug("Nu s-au putut seta handlere de semnal: %s", exc)

    def _handle_os_signal(self, signum: int, frame: Any) -> None:
        """Tratează semnalele de terminare (Ctrl+C, SIGTERM)."""
        logger.warning("[Hardware] Semnal OS recepționat (%s)! Oprire imediată de siguranță...", signum)
        self.emergency_stop()
        sys.exit(0)

    def heartbeat(self) -> None:
        """Notifică watchdog-ul că bucla principală rulează normal."""
        self._last_heartbeat = time.time()

    def _watchdog_loop(self) -> None:
        """Thread independent de watchdog (verificare la fiecare 500 ms)."""
        while self._watchdog_active:
            now = time.time()
            elapsed_hb = now - self._last_heartbeat

            # 1. Verificare timeout buclă de control
            if (
                elapsed_hb > self.cfg.watchdog_timeout_s
                and not self._emergency_stopped
                and (self._pump_state or self._peltier_state)
            ):
                logger.critical(
                    "[WATCHDOG] Heartbeat absent de %.2fs (> %.1fs)! Decuplare forțată actuatori!",
                    elapsed_hb,
                    self.cfg.watchdog_timeout_s,
                )
                self.emergency_stop()

            # 2. Verificare limită timp continuu Peltier (max 5 min)
            with self._lock:
                if self._peltier_state and self._peltier_on_start_time is not None:
                    on_duration = now - self._peltier_on_start_time
                    if on_duration > self.cfg.peltier_max_continuous_s:
                        logger.warning(
                            "[SAFETY] Peltier activ continuu de %.1fs (> %.1fs)! Decuplare automată de protecție.",
                            on_duration,
                            self.cfg.peltier_max_continuous_s,
                        )
                        self.set_peltier(False)

            time.sleep(0.5)

    def check_thermal_limit(self, hot_side_temp_c: float | None) -> None:
        """Decuplează Peltierul dacă temperatura radiatorului cald depășește limita de delaminare."""
        if hot_side_temp_c is None:
            return

        if hot_side_temp_c >= self.cfg.peltier_hot_limit_c and self._peltier_state:
            logger.critical(
                "[SAFETY] Radiator cald la %.1f°C (>= %.1f°C)! Oprire de urgență Peltier!",
                hot_side_temp_c,
                self.cfg.peltier_hot_limit_c,
            )
            self.set_peltier(False)
        elif hot_side_temp_c >= self.cfg.peltier_hot_warn_c:
            logger.warning(
                "[SAFETY] Radiator cald la %.1f°C (>= %.1f°C avertizare)",
                hot_side_temp_c,
                self.cfg.peltier_hot_warn_c,
            )

    @property
    def pump_enabled(self) -> bool:
        return self._pump_enabled

    @pump_enabled.setter
    def pump_enabled(self, value: bool) -> None:
        with self._lock:
            self._pump_enabled = bool(value)
            if not self._pump_enabled and self._pump_state:
                logger.info("[Hardware] Pompă dezactivată din configurație: oprire imediată.")
                self.set_pump(False)

    def set_pump(self, turn_on: bool, speed_pct: float = 100.0) -> None:
        """Setează starea pompei respectând flag-ul de siguranță pump_enabled."""
        with self._lock:
            if self._emergency_stopped:
                return

            if turn_on and not self._pump_enabled:
                # Comanda este ignorată în siguranță dacă pompa este dezactivată împotriva mersului în gol
                self._pump_state = False
                self._pump_speed_pct = 0.0
                if self._pump is not None:
                    try:
                        self._pump.turn_off()
                    except Exception as exc:  # noqa: BLE001
                        logger.debug("Eroare oprire pompă: %s", exc)
                return

            self._pump_state = bool(turn_on)
            self._pump_speed_pct = max(0.0, min(100.0, float(speed_pct))) if turn_on else 0.0

            if self._pump is not None:
                try:
                    if self._pump_state:
                        self._pump.turn_on(self._pump_speed_pct)
                    else:
                        self._pump.turn_off()
                except Exception as exc:  # noqa: BLE001
                    logger.error("[Hardware] Eroare comandă pompă: %s", exc)

    def set_peltier(self, turn_on: bool) -> None:
        """Activează sau dezactivează modulul Peltier cu contorizare de timp."""
        with self._lock:
            if self._emergency_stopped:
                return

            was_on = self._peltier_state
            self._peltier_state = bool(turn_on)

            if self._peltier_state and not was_on:
                self._peltier_on_start_time = time.time()
            elif not self._peltier_state:
                self._peltier_on_start_time = None

            if self._peltier is not None:
                try:
                    self._peltier.apply(self._peltier_state)
                except Exception as exc:  # noqa: BLE001
                    logger.error("[Hardware] Eroare comandă Peltier: %s", exc)

    def stop_all(self) -> None:
        """Oprește ambii actuatori în mod normal."""
        with self._lock:
            self._pump_state = False
            self._pump_speed_pct = 0.0
            self._peltier_state = False
            self._peltier_on_start_time = None

            if self._pump is not None:
                try:
                    self._pump.stop()
                except Exception as exc:  # noqa: BLE001
                    logger.debug("Eroare stop pompă: %s", exc)
            if self._peltier is not None:
                try:
                    self._peltier.stop()
                except Exception as exc:  # noqa: BLE001
                    logger.debug("Eroare stop Peltier: %s", exc)

    def emergency_stop(self) -> None:
        """STOP DE URGENȚĂ (Tasta S / Blocare): oprire forțată și blocare comenzi."""
        with self._lock:
            self._emergency_stopped = True
            self.stop_all()
            logger.critical("[Hardware] !!! STOP DE URGENȚĂ ACTIVAT — TOȚI ACTUATORII OPRITI !!!")

    def reset_emergency_stop(self) -> None:
        """Resetează starea de avarie după confirmare."""
        with self._lock:
            self._emergency_stopped = False
            self.stop_all()
            self.heartbeat()
            logger.info("[Hardware] Stop de urgență resetat.")

    @property
    def is_emergency_stopped(self) -> bool:
        return self._emergency_stopped

    @property
    def pump_state(self) -> bool:
        return self._pump_state

    @property
    def pump_speed_pct(self) -> float:
        return self._pump_speed_pct

    @property
    def peltier_state(self) -> bool:
        return self._peltier_state

    def close(self) -> None:
        """Închide watchdog-ul și eliberează resursele GPIO."""
        self._watchdog_active = False
        self.emergency_stop()
        if self._pump is not None:
            try:
                self._pump.close()
            except Exception as exc:  # noqa: BLE001
                logger.debug("Eroare închidere pompă: %s", exc)
        if self._peltier is not None:
            try:
                self._peltier.close()
            except Exception as exc:  # noqa: BLE001
                logger.debug("Eroare închidere Peltier: %s", exc)
