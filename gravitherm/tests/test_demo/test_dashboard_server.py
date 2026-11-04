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
        assert len(result) == 44
        assert isinstance(result[0], str)
        assert ":" in result[0]  # format oră HH:MM

        # Verificare că figurile nu au titlu intern Plotly (titlurile sunt HTML)
        fig_pper = result[34]
        fig_temp = result[35]
        fig_grid = result[36]
        assert fig_pper.layout.title.text is None
        assert fig_temp.layout.title.text is None
        assert fig_grid.layout.title.text is None

        # Verificare inițială buton pauză
        assert result[10] == "Pauză (P)"
    finally:
        eng.close()


def test_dashboard_controls_and_feedback():
    """Verifică legarea acțiunilor și tastelor: pauză/reluare, avansare fază, stop de urgență și toast."""
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
        user_fn = getattr(fn, "__wrapped__", fn)

        # 1. Test pauză prin toggle_pause / tasta P
        eng.toggle_pause()
        res_paused = user_fn(2)
        assert res_paused[10] == "Reia (P)"
        assert res_paused[13] == "Pauză activată"

        # 2. Test reluare
        eng.toggle_pause()
        res_resumed = user_fn(3)
        assert res_resumed[10] == "Pauză (P)"
        assert res_resumed[13] == "Simulare reluată"

        # 3. Test avansare faza prin Space / next_phase
        eng.next_phase()
        res_p1 = user_fn(4)
        assert "Faza 1" in res_p1[1]
        assert "Faza 1 pornită" in res_p1[13]

        # 4. Test STOP de urgență prin tasta S / buton STOP
        eng.emergency_stop()
        res_stop = user_fn(5)
        assert res_stop[13] == "STOP DE URGENȚĂ ACTIVAT"
        # Verificare că actuatorii sunt forțați pe OPRITĂ / OPRIT
        assert res_stop[29] == "OPRITĂ"
        assert res_stop[31] == "OPRIT"
        assert res_stop[4] == "POMPĂ OFF"
        assert res_stop[6] == "UTL OFF"
    finally:
        eng.close()

