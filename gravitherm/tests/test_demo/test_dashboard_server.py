"""Test de integrare pentru pornirea serverului Dash și servirea paginii HTML."""

import threading
import time
import urllib.request

from gravitherm.demo.dashboard import create_demo_dashboard
from gravitherm.demo.data_model import DataModel
from gravitherm.demo.demo_config import DemoConfig
from gravitherm.demo.engine import DemoEngine
from gravitherm.demo.hardware import HardwareManager


def test_dashboard_page_serves_html():
    """Verifică pornirea serverului Dash, servirea paginii cu cod 200 și prezența elementelor principale."""
    cfg = DemoConfig()
    hw = HardwareManager(mock_mode=True)
    dm = DataModel(config=cfg, mock_mode=True)
    eng = DemoEngine(hardware=hw, data_model=dm, config=cfg, auto_advance=False)

    try:
        eng.start()
        app = create_demo_dashboard(engine=eng, data_model=dm, config=cfg)

        server_port = 8066
        server_thread = threading.Thread(
            target=lambda: app.run(host="127.0.0.1", port=server_port, debug=False),
            daemon=True,
        )
        server_thread.start()
        time.sleep(1.5)

        # 1. Pagină principală HTML (shell React)
        with urllib.request.urlopen(f"http://127.0.0.1:{server_port}/") as resp:
            assert resp.status == 200
            content = resp.read().decode("utf-8")
            assert "GraviTherm · Demo Live" in content
            assert "key-press-input" in content

        # 2. Endpoint layout Dash (componentele arborelui React)
        with urllib.request.urlopen(f"http://127.0.0.1:{server_port}/_dash-layout") as resp:
            assert resp.status == 200
            layout_json = resp.read().decode("utf-8")
            assert "demo-interval" in layout_json
            assert "agent-decisions-panel" in layout_json
    finally:
        eng.close()


def test_dashboard_callback_execution():
    """Verifică execuția callback-ului principal fără erori (fără KeyError sau crash)."""
    cfg = DemoConfig()
    hw = HardwareManager(mock_mode=True)
    dm = DataModel(config=cfg, mock_mode=True)
    eng = DemoEngine(hardware=hw, data_model=dm, config=cfg, auto_advance=False)

    try:
        eng.start()
        app = create_demo_dashboard(engine=eng, data_model=dm, config=cfg)

        fn = None
        for k, v in app.callback_map.items():
            if "clock-display.children" in str(k):
                fn = v["callback"]
                break

        assert fn is not None, "Callback-ul update_dashboard_views nu a fost găsit"
        user_fn = getattr(fn, "__wrapped__", fn)
        result = user_fn(1)
        assert len(result) == 39
        assert isinstance(result[0], str)
        assert ":" in result[0]  # format oră HH:MM
    finally:
        eng.close()

