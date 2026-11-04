"""Motorul de scenariu și mașina de stări pentru Demo Live GraviTherm.

Gestionează:
- avansul ceasului simulat de la 00:00 la 24:00 prin cele 6 faze;
- comanda actuatorilor reali / mock;
- stările: RUNNING, PAUSED, PHASE_COMPLETED, EMERGENCY_STOPPED;
- controalele din tastatură (Space/Săgeată dreapta, P, R, S) și din terminal (stdin);
- bucla periodică de execuție la ~2 Hz.
"""

from __future__ import annotations

import logging
import select
import sys
import threading
import time
from enum import Enum
from typing import Any

from gravitherm.demo.data_model import DataModel
from gravitherm.demo.demo_config import DemoConfig
from gravitherm.demo.hardware import HardwareManager
from gravitherm.demo.scenario import PhaseDefinition, get_all_phases, get_simulated_targets

logger = logging.getLogger("gravitherm.demo.engine")


class EngineState(str, Enum):
    INITIALIZING = "INITIALIZING"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    PHASE_COMPLETED = "PHASE_COMPLETED"
    EMERGENCY_STOPPED = "EMERGENCY_STOPPED"
    FINISHED = "FINISHED"


class DemoEngine:
    """Motorul principal de rulare al scenariului demo."""

    def __init__(
        self,
        hardware: HardwareManager,
        data_model: DataModel,
        config: DemoConfig | None = None,
        auto_advance: bool = False,
    ) -> None:
        self.cfg = config or DemoConfig()
        self.hw = hardware
        self.dm = data_model
        self.auto_advance = auto_advance

        self._lock = threading.RLock()
        self.phases = get_all_phases(self.cfg)
        self.current_phase_idx: int = 0

        self.state: EngineState = EngineState.INITIALIZING
        self.phase_elapsed_s: float = 0.0
        self.sim_hour: float = 0.0

        # Stare modal sumar și popover confirmare
        self.summary_modal_open: bool = False
        self.reset_confirm_open: bool = False
        self.summary_closed_by_user: bool = False

        self._running: bool = True
        self._dt_s: float = 1.0 / max(self.cfg.engine_tick_hz, 0.5)

        # Thread principal de execuție periodică
        self._thread = threading.Thread(target=self._loop, name="DemoEngineLoop", daemon=True)

        # Thread opțional de ascultare tastatură pe stdin (terminal)
        self._stdin_thread = threading.Thread(target=self._stdin_listener, name="StdinListener", daemon=True)

    def start(self) -> None:
        """Pornește motorul și buclele de rulare."""
        with self._lock:
            self.state = EngineState.RUNNING
            self.current_phase_idx = 0
            self.phase_elapsed_s = 0.0
            self.sim_hour = self.phases[0].start_hour
            self.dm.reset()
            self._thread.start()
            self._stdin_thread.start()
            logger.info("[ENGINE] Motor pornit în starea RUNNING la Faza 0.")

    @property
    def current_phase(self) -> PhaseDefinition:
        with self._lock:
            return self.phases[self.current_phase_idx]

    def next_phase(self) -> None:
        """Avansează la faza următoare (la comanda prezentatorului — tasta Space)."""
        with self._lock:
            if self.state == EngineState.EMERGENCY_STOPPED:
                logger.warning("[ENGINE] Nu se poate avansa: sistemul este în STOP DE URGENȚĂ (apăsați R).")
                return

            if self.state == EngineState.FINISHED:
                return

            if self.current_phase_idx < len(self.phases) - 1:
                self.current_phase_idx += 1
                self.phase_elapsed_s = 0.0
                next_p = self.phases[self.current_phase_idx]
                self.sim_hour = next_p.start_hour
                self.state = EngineState.RUNNING
                logger.info(
                    "[ENGINE] Avansat la %s (start ora %.1f:00)",
                    next_p.name,
                    next_p.start_hour,
                )
            else:
                self.state = EngineState.FINISHED
                logger.info("[ENGINE] Scenariu finalizat (Faza 5 încheiată).")

    def toggle_pause(self) -> None:
        """Pauză / reluare ceas simulat (tasta P)."""
        with self._lock:
            if self.state == EngineState.RUNNING:
                self.state = EngineState.PAUSED
                logger.info("[ENGINE] PAUZĂ: ceas simulat înghețat, actuatori menținuți.")
            elif self.state == EngineState.PAUSED:
                self.state = EngineState.RUNNING
                logger.info("[ENGINE] RELUARE: ceasul simulat avansează.")

    def reset(self) -> None:
        """Resetează scenariul la Faza 0 (tasta R)."""
        with self._lock:
            self.hw.reset_emergency_stop()
            self.current_phase_idx = 0
            self.phase_elapsed_s = 0.0
            self.sim_hour = self.phases[0].start_hour
            self.state = EngineState.RUNNING
            self.summary_modal_open = False
            self.reset_confirm_open = False
            self.summary_closed_by_user = False
            self.dm.reset()
            logger.info("[ENGINE] RESET la Faza 0 (totul oprit, date șterse).")

    def emergency_stop(self) -> None:
        """STOP DE URGENȚĂ imediat (tasta S)."""
        with self._lock:
            self.state = EngineState.EMERGENCY_STOPPED
            self.hw.emergency_stop()
            self.dm.log_decision("STOP DE URGENȚĂ — Actuatori decuplați imediat!")
            logger.critical("[ENGINE] STOP DE URGENȚĂ apelat din motor!")

    def set_pump_enabled(self, enabled: bool) -> None:
        """Activează sau dezactivează pompa în runtime."""
        with self._lock:
            self.hw.pump_enabled = enabled
            self.dm.log_decision(f"Comutare protecție pompă: {'ACTIVATĂ' if enabled else 'DEZACTIVATĂ'}")

    def _loop(self) -> None:
        """Bucla periodică a motorului de scenariu (~2 Hz)."""
        last_tick = time.time()

        while self._running:
            now = time.time()
            elapsed_loop = now - last_tick
            if elapsed_loop < self._dt_s:
                time.sleep(max(0.005, self._dt_s - elapsed_loop))
                now = time.time()

            actual_dt = now - last_tick
            last_tick = now

            # Heartbeat watchdog la fiecare pas
            self.hw.heartbeat()

            with self._lock:
                phase = self.phases[self.current_phase_idx]

                if self.state == EngineState.RUNNING:
                    self.phase_elapsed_s += actual_dt

                    # Fracțiune din faza curentă
                    dur = max(phase.duration_s, 0.1)
                    fraction = min(1.0, self.phase_elapsed_s / dur)

                    # Ora simulată avansează liniar și monoton în interiorul fazei
                    self.sim_hour = phase.start_hour + fraction * (phase.end_hour - phase.start_hour)

                    # Calcul ținte fază
                    targets = get_simulated_targets(
                        phase=phase,
                        fraction_in_phase=fraction,
                        wall_elapsed_in_phase=self.phase_elapsed_s,
                        config=self.cfg,
                    )

                    # Comandă hardware
                    self.hw.set_pump(bool(targets["pump_target"]), float(targets["pump_speed_pct"]))
                    self.hw.set_peltier(bool(targets["peltier_target"]))

                    # Pas model de date
                    pt = self.dm.step(
                        phase=phase,
                        fraction_in_phase=fraction,
                        wall_elapsed_in_phase=self.phase_elapsed_s,
                        sim_hour=self.sim_hour,
                        dt_s=actual_dt,
                        actual_pump_on=self.hw.pump_state,
                        actual_pump_speed_pct=self.hw.pump_speed_pct,
                        actual_peltier_on=self.hw.peltier_state,
                    )

                    # Verificare limită termică Peltier
                    self.hw.check_thermal_limit(pt.temp_hot_side)

                    # Verificare final fază
                    if self.phase_elapsed_s >= phase.duration_s:
                        if self.auto_advance and self.current_phase_idx < len(self.phases) - 1:
                            self.next_phase()
                        else:
                            # Atingere final de fază: oprire discretă și afișare mesaj așteptare
                            self.state = EngineState.PHASE_COMPLETED
                            self.sim_hour = phase.end_hour
                            logger.info(
                                "[ENGINE] Faza %d finalizată. Așteptare Space pentru următoarea fază.",
                                phase.phase_id,
                            )

                elif self.state in (EngineState.PAUSED, EngineState.PHASE_COMPLETED):
                    # În pauză sau la final de fază: actualizăm datele la ora fixă fără a avansa ceasul
                    fraction = (
                        1.0
                        if self.state == EngineState.PHASE_COMPLETED
                        else (self.phase_elapsed_s / max(phase.duration_s, 0.1))
                    )
                    self.dm.step(
                        phase=phase,
                        fraction_in_phase=fraction,
                        wall_elapsed_in_phase=self.phase_elapsed_s,
                        sim_hour=self.sim_hour,
                        dt_s=actual_dt,
                        actual_pump_on=self.hw.pump_state,
                        actual_pump_speed_pct=self.hw.pump_speed_pct,
                        actual_peltier_on=self.hw.peltier_state,
                    )

                elif self.state == EngineState.EMERGENCY_STOPPED:
                    # Asigurare suplimentară oprire
                    self.hw.stop_all()

    def _stdin_listener(self) -> None:
        """Ascultă taste din terminal (stdin) ca rezervă suplimentară pentru prezentator."""
        while self._running:
            try:
                # Verificare portabilă pe platforme POSIX/Linux (pe RPi / WSL)
                if hasattr(select, "select") and sys.stdin is not None:
                    try:
                        rlist, _, _ = select.select([sys.stdin], [], [], 0.5)
                        if rlist:
                            line = sys.stdin.readline()
                            if not line:
                                # EOF pe stdin (ex: fundal, non-interactiv)
                                break
                            clean_line = line.strip().lower()
                            if clean_line:
                                self.handle_command_string(clean_line)
                            elif line in ("\n", "\r\n"):
                                self.next_phase()
                    except (OSError, ValueError) as exc:
                        logger.debug("Eroare select stdin: %s", exc)
                        time.sleep(0.5)
                else:
                    time.sleep(1.0)
            except (OSError, ValueError) as exc:
                logger.debug("Închidere ascultător stdin: %s", exc)
                break

    def handle_command_string(self, cmd: str) -> None:
        """Procesează comenzile primite din browser (taste) sau terminal."""
        clean_cmd = cmd.strip().lower()
        if not clean_cmd:
            return

        if clean_cmd in (" ", "space", "arrowright", "next", "n"):
            self.next_phase()
        elif clean_cmd in ("p", "pause", "keyp"):
            self.toggle_pause()
        elif clean_cmd in ("r", "reset", "keyr"):
            self.reset()
        elif clean_cmd in ("s", "stop", "keys", "emergency"):
            self.emergency_stop()
        elif clean_cmd in ("escape", "esc", "close"):
            self.close_summary()
        elif clean_cmd in ("t", "sumar", "summary"):
            self.open_summary()

    def close_summary(self) -> None:
        """Închide overlay-ul de sumar la cererea utilizatorului."""
        with self._lock:
            self.summary_modal_open = False
            self.summary_closed_by_user = True

    def open_summary(self) -> None:
        """Redeschide overlay-ul de sumar la cererea utilizatorului."""
        with self._lock:
            self.summary_modal_open = True

    def request_reset_confirm(self) -> None:
        """Afișează popoverul de confirmare pentru reluarea demo-ului."""
        with self._lock:
            self.reset_confirm_open = True

    def cancel_reset_confirm(self) -> None:
        """Închide popoverul de confirmare a resetării."""
        with self._lock:
            self.reset_confirm_open = False

    def get_status_dict(self) -> dict[str, Any]:
        """Returnează starea curentă a motorului pentru dashboard."""
        with self._lock:
            phase = self.phases[self.current_phase_idx]

            # Formatare oră simulată HH:MM
            h_int = int(self.sim_hour)
            m_int = int((self.sim_hour - h_int) * 60)
            sim_time_str = f"{h_int:02d}:{m_int:02d}" if h_int < 24 else "24:00"

            # Auto-deschidere sumar în Faza 5 dacă nu a fost închis explicit
            if self.current_phase_idx == 5 and not self.summary_closed_by_user:
                self.summary_modal_open = True

            return {
                "state": self.state.value,
                "phase_id": phase.phase_id,
                "phase_name": phase.name,
                "phase_short": phase.short_title,
                "phase_decision": phase.decision_text,
                "sim_hour": round(self.sim_hour, 2),
                "sim_time_str": sim_time_str,
                "phase_elapsed_s": round(self.phase_elapsed_s, 1),
                "phase_duration_s": phase.duration_s,
                "wall_elapsed_s": round(self.phase_elapsed_s, 1),
                "auto_advance": self.auto_advance,
                "waiting_for_next": self.state == EngineState.PHASE_COMPLETED,
                "pump_active": self.hw.pump_state,
                "actual_pump_on": self.hw.pump_state,
                "pump_speed_pct": round(self.hw.pump_speed_pct, 1),
                "pump_enabled": self.hw.pump_enabled,
                "peltier_active": self.hw.peltier_state,
                "actual_peltier_on": self.hw.peltier_state,
                "is_emergency": self.hw.is_emergency_stopped,
                "summary_modal_open": self.summary_modal_open,
                "reset_confirm_open": self.reset_confirm_open,
            }

    def close(self) -> None:
        """Oprește motorul și eliberează resursele."""
        self._running = False
        self.emergency_stop()
        self.hw.close()
        self.dm.close()
