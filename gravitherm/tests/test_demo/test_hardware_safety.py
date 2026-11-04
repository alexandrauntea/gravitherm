"""Teste unitare pentru mecanismele de siguranță hardware și oprire de urgență."""

import time

from gravitherm.demo.demo_config import DemoConfig
from gravitherm.demo.hardware import HardwareManager


def test_initial_state_and_safe_defaults():
    """La pornire ambii actuatori trebuie să fie garantați în starea OPRIT."""
    hw = HardwareManager(mock_mode=True)
    try:
        assert hw.pump_state is False
        assert hw.pump_speed_pct == 0.0
        assert hw.peltier_state is False
        assert hw.is_emergency_stopped is False
    finally:
        hw.close()


def test_pump_dry_run_protection():
    """Dacă pump_enabled=False, pompa nu poate fi pornită (protecție împotriva mersului în gol)."""
    cfg = DemoConfig(pump_enabled=False)
    hw = HardwareManager(config=cfg, mock_mode=True)
    try:
        hw.set_pump(turn_on=True, speed_pct=100.0)
        assert hw.pump_state is False
        assert hw.pump_speed_pct == 0.0

        # Când utilizatorul activează pompa (runtime toggle)
        hw.pump_enabled = True
        hw.set_pump(turn_on=True, speed_pct=100.0)
        assert hw.pump_state is True
        assert hw.pump_speed_pct == 100.0

        # Când o dezactivează, se oprește imediat
        hw.pump_enabled = False
        assert hw.pump_state is False
    finally:
        hw.close()


def test_emergency_stop_mechanism():
    """Tasta S / Emergency Stop trebuie să oprească instant totul și să blocheze comenzile."""
    cfg = DemoConfig(pump_enabled=True)
    hw = HardwareManager(config=cfg, mock_mode=True)
    try:
        hw.set_pump(True, 100.0)
        hw.set_peltier(True)
        assert hw.pump_state is True
        assert hw.peltier_state is True

        # Declanșare STOP DE URGENȚĂ
        hw.emergency_stop()
        assert hw.is_emergency_stopped is True
        assert hw.pump_state is False
        assert hw.peltier_state is False

        # Comenzile ulterioare sunt ignorate
        hw.set_pump(True, 100.0)
        hw.set_peltier(True)
        assert hw.pump_state is False
        assert hw.peltier_state is False

        # Resetare
        hw.reset_emergency_stop()
        assert hw.is_emergency_stopped is False
    finally:
        hw.close()


def test_thermal_limit_safety():
    """Peltier-ul trebuie decuplat automat dacă radiatorul depășește limita de 60°C."""
    hw = HardwareManager(mock_mode=True)
    try:
        hw.set_peltier(True)
        assert hw.peltier_state is True

        # Temperatură caldă normală (45°C) -> rămâne ON
        hw.check_thermal_limit(45.0)
        assert hw.peltier_state is True

        # Temperatură peste limită (61.5°C) -> oprire de siguranță!
        hw.check_thermal_limit(61.5)
        assert hw.peltier_state is False
    finally:
        hw.close()


def test_watchdog_timeout():
    """Watchdog-ul independent decuplează actuatorii dacă bucla nu mai oferă heartbeat."""
    cfg = DemoConfig(pump_enabled=True, watchdog_timeout_s=1.0)
    hw = HardwareManager(config=cfg, mock_mode=True)
    try:
        hw.set_pump(True, 100.0)
        assert hw.pump_state is True

        # Simulăm înghețarea buclei principale (fără heartbeat timp de 1.5s)
        time.sleep(1.5)

        # Watchdog-ul trebuie să fi activat emergency_stop
        assert hw.is_emergency_stopped is True
        assert hw.pump_state is False
    finally:
        hw.close()
