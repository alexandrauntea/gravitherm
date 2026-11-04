#!/usr/bin/env python3
"""Punct de intrare pentru Demo-ul Live GraviTherm (Etapa II, TechChallenge Honeywell 2026).

Comandă hardware-ul de pe Raspberry Pi 4 (sau mock pe laptop) și servește
dashboard-ul Plotly Dash în limba română la http://<ip>:8050.

Rulare:
    python scripts/demo_live.py                    # Hardware real (cu siguranță pompă)
    python scripts/demo_live.py --enable-pump      # Hardware real cu pompă activată
    python scripts/demo_live.py --mock             # Laptop / repetiții (actuatori virtuali)
    python scripts/demo_live.py --mock --auto      # Mod automat cap-coadă
"""

from __future__ import annotations

import argparse
import logging
import os
import socket
import sys

# Asigurare import gravitherm indiferent de calea de pornire
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from gravitherm.demo.dashboard import create_demo_dashboard
from gravitherm.demo.data_model import DataModel
from gravitherm.demo.demo_config import DemoConfig
from gravitherm.demo.engine import DemoEngine
from gravitherm.demo.hardware import HardwareManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("gravitherm.demo")


def get_local_ip() -> str:
    """Detectează IP-ul local pentru afișarea URL-ului în consolă."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return str(ip)
    except OSError:
        return "127.0.0.1"


def print_banner(host: str, port: int, mock: bool, pump_enabled: bool, auto: bool) -> None:
    local_ip = get_local_ip()
    mode_str = "MOCK (Laptop / Fără hardware)" if mock else "HARDWARE REAL (Raspberry Pi 4)"
    pump_str = "ACTIVATĂ (Atenție la apă!)" if pump_enabled else "DEZACTIVATĂ (Siguranță mers în gol)"
    nav_str = "AUTOMAT (--auto)" if auto else "MANUAL (Space / Săgeată Dreapta)"

    print("=" * 72)
    print("      ██████╗ ██████╗  █████╗ ██╗   ██╗██╗████████╗██╗  ██╗███████╗██████╗ ███╗   ███╗")
    print("     ██╔════╝ ██╔══██╗██╔══██╗██║   ██║██║╚══██╔══╝██║  ██║██╔════╝██╔══██╗████╗ ████║")
    print("     ██║  ███╗██████╔╝███████║██║   ██║██║   ██║   ███████║█████╗  ██████╔╝██╔████╔██║")
    print("     ██║   ██║██╔══██╗██╔══██║╚██╗ ██╔╝██║   ██║   ██╔══██║██╔══╝  ██╔══██╗██║╚██╔╝██║")
    print("     ╚██████╔╝██║  ██║██║  ██║ ╚████╔╝ ██║   ██║   ██║  ██║███████╗██║  ██║██║ ╚═╝ ██║")
    print("      ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝  ╚═══╝  ╚═╝   ╚═╝   ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝╚═╝     ╚═╝")
    print("               Etapa II · TechChallenge by Honeywell 2026")
    print("=" * 72)
    print(f"  • Mod rulare       : {mode_str}")
    print(f"  • Stare Pompă      : {pump_str}")
    print(f"  • Control Faze     : {nav_str}")
    print(f"  • Dashboard Local  : http://localhost:{port}")
    print(f"  • Dashboard Rețea  : http://{local_ip}:{port}")
    print("-" * 72)
    print("  COMENZI DIN TASTATURĂ (în browser sau în acest terminal):")
    print("    [Space] sau [→]  : Faza următoare (avansează la următoarea etapă)")
    print("    [P]              : Pauză / Reluare ceas simulat")
    print("    [R]              : Reset complet la Faza 0")
    print("    [S]              : STOP DE URGENȚĂ (oprește instant pompa și Peltierul)")
    print("=" * 72)
    print("Pornire server Dash... Apăsați Ctrl+C pentru oprire sigură.\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Script Demo Live GraviTherm")
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Rulează în mod MOCK (fără componente hardware, pentru laptop/repetiții)",
    )
    parser.add_argument(
        "--auto",
        action="store_true",
        help="Avansează automat fazele la expirarea timpului alocat (mod de rezervă)",
    )
    parser.add_argument(
        "--enable-pump",
        action="store_true",
        help="Activează pompa la pornire (dacă lipsește, pompa este blocată software împotriva mersului în gol)",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="Adresă host server Dash (implicit: 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8050,
        help="Port server Dash (implicit: 8050)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    config = DemoConfig()
    if args.enable_pump:
        config.pump_enabled = True

    hardware = HardwareManager(config=config, mock_mode=args.mock)
    data_model = DataModel(config=config, mock_mode=args.mock)
    engine = DemoEngine(
        hardware=hardware,
        data_model=data_model,
        config=config,
        auto_advance=args.auto,
    )

    dashboard_app = create_demo_dashboard(engine=engine, data_model=data_model, config=config)

    print_banner(
        host=args.host,
        port=args.port,
        mock=args.mock,
        pump_enabled=config.pump_enabled,
        auto=args.auto,
    )

    try:
        engine.start()
        # Rulare server Dash fără reîncărcare automată (pentru stabilitate thread-uri pe RPi)
        dashboard_app.run(
            host=args.host,
            port=args.port,
            debug=False,
        )
    except (KeyboardInterrupt, SystemExit):
        logger.info("\nOprire sesiune demo...")
    finally:
        engine.close()
        logger.info("Demo oprit în siguranță.")


if __name__ == "__main__":
    main()
