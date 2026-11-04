"""Dashboard Plotly Dash pentru Demo Live GraviTherm (în limba română).

Proiectat pentru videoproiector (16:9, fără scroll la 1920x1080):
- schemă animată SVG clădire 3D (flux apă, rotație turbină, strălucire LED, buclă UTL);
- ceas digital mare cu ora simulată și badge fază;
- 5 carduri KPI (fonturi >= 48px);
- 3 grafice sincronizate pe axa fixă 00:00 - 24:00;
- ecran mare de sumar (Faza 5) cu impact anual și CO2;
- comenzi rapide de la tastatură (Space, P, R, S) prin clientside callback.
"""

from __future__ import annotations

import logging
from typing import Any

import dash
import plotly.graph_objects as go
from dash import Input, Output, clientside_callback, dcc, html

from gravitherm.demo.data_model import DataModel, TelemetryPoint
from gravitherm.demo.demo_config import DemoConfig
from gravitherm.demo.engine import DemoEngine, EngineState

logger = logging.getLogger("gravitherm.demo.dashboard")

# Stiluri globale CSS injectate inline
CUSTOM_CSS = """
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;800&family=Plus+Jakarta+Sans:wght@400;600;700;800&display=swap');

* {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
    font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
    -webkit-font-smoothing: antialiased;
}

body {
    background-color: #07090e;
    color: #f1f5f9;
    overflow-x: hidden;
    overflow-y: auto;
}

.mono-font {
    font-family: 'JetBrains Mono', monospace;
}

/* Animații CSS pentru schema SVG */
@keyframes pipeFlow {
    0% { stroke-dashoffset: 40; }
    100% { stroke-dashoffset: 0; }
}

@keyframes spinTurbine {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
}

@keyframes pulsePeltier {
    0%, 100% { filter: drop-shadow(0 0 6px #06d6a0); opacity: 0.75; }
    50% { filter: drop-shadow(0 0 18px #2ec4b6); opacity: 1.0; }
}

@keyframes ledGlow {
    0%, 100% { filter: drop-shadow(0 0 10px #facc15); opacity: 0.85; }
    50% { filter: drop-shadow(0 0 24px #fef08a); opacity: 1.0; }
}

@keyframes livePulse {
    0%, 100% { opacity: 1.0; transform: scale(1.0); }
    50% { opacity: 0.35; transform: scale(0.92); }
}

@keyframes waitingBlink {
    0%, 100% { opacity: 1.0; }
    50% { opacity: 0.25; }
}

.pipe-running {
    stroke-dasharray: 8 6;
    animation: pipeFlow 0.8s linear infinite;
}

.turbine-running {
    transform-origin: 190px 240px;
    animation: spinTurbine 1.2s linear infinite;
}

.peltier-running {
    animation: pulsePeltier 2.0s ease-in-out infinite;
}

.led-on {
    animation: ledGlow 1.2s ease-in-out infinite;
}

.live-dot {
    display: inline-block;
    width: 10px;
    height: 10px;
    background-color: #ef4444;
    border-radius: 50%;
    margin-right: 6px;
    animation: livePulse 1.5s infinite;
}

.waiting-badge {
    animation: waitingBlink 1.5s infinite;
}

/* Carduri Glassmorphism */
.glass-card {
    background: rgba(15, 23, 42, 0.75);
    backdrop-filter: blur(8px);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 12px;
    padding: 12px 16px;
}

.kpi-card {
    background: linear-gradient(135deg, rgba(30, 41, 59, 0.7) 0%, rgba(15, 23, 42, 0.85) 100%);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 12px;
    padding: 10px 14px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
}

.btn-ctrl {
    background: rgba(30, 41, 59, 0.85);
    border: 1px solid rgba(255, 255, 255, 0.15);
    color: #f8fafc;
    border-radius: 8px;
    padding: 6px 12px;
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s ease;
}

.btn-ctrl:hover {
    background: rgba(51, 65, 85, 0.95);
    border-color: rgba(255, 255, 255, 0.3);
}

.btn-emergency {
    background: rgba(220, 38, 38, 0.85);
    border: 1px solid #ef4444;
}

.btn-emergency:hover {
    background: rgba(239, 68, 68, 1.0);
}
"""


def create_demo_dashboard(
    engine: DemoEngine, data_model: DataModel, config: DemoConfig | None = None
) -> dash.Dash:
    """Construiește și configurează aplicația Dash pentru demo-ul live."""
    cfg = config or DemoConfig()

    app = dash.Dash(
        __name__,
        title="GraviTherm · Demo Live",
        update_title=None,
    )

    # SVG-ul interactiv al clădirii
    def render_building_svg(pt: TelemetryPoint | None) -> html.Div:
        pump_on = pt.pump_active if pt else False
        peltier_on = pt.peltier_active if pt else False
        press_val = f"{pt.pressure_kpa:.1f} kPa" if pt else "0.0 kPa"
        flow_val = f"{pt.flow_l_min:.2f} L/min" if pt else "0.00 L/min"
        p_extrap = f"{pt.power_pper_extrapolated_w:.1f} W" if pt else "0.0 W"
        p_lab = f"{pt.power_pper_lab_mw:.0f} mW" if pt else "0 mW"

        pipe_class = "pipe-running" if pump_on else ""
        turbine_class = "turbine-running" if pump_on else ""
        peltier_class = "peltier-running" if peltier_on else ""
        led_class = "led-on" if pump_on else ""

        svg_content = f"""
        <svg viewBox="0 0 460 380" width="100%" height="100%" xmlns="http://www.w3.org/2000/svg">
            <defs>
                <linearGradient id="buildingGrad" x1="0" y1="0" x2="1" y2="0">
                    <stop offset="0%" stop-color="#1e293b" stop-opacity="0.9"/>
                    <stop offset="100%" stop-color="#0f172a" stop-opacity="0.95"/>
                </linearGradient>
                <linearGradient id="soilGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stop-color="#1c1917" stop-opacity="0.9"/>
                    <stop offset="100%" stop-color="#0c0a09" stop-opacity="0.98"/>
                </linearGradient>
                <linearGradient id="waterFlowGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stop-color="#38bdf8"/>
                    <stop offset="100%" stop-color="#0284c7"/>
                </linearGradient>
            </defs>

            <!-- Zona Sol UTL (5-8 m adâncime) -->
            <rect x="20" y="275" width="420" height="95" rx="8" fill="url(#soilGrad)" stroke="#44403c" stroke-width="1.5"/>
            <text x="35" y="295" fill="#a8a29e" font-size="11" font-weight="600">SOL UTL (5-8 m) · 13°C Constant</text>

            <!-- Bucla de apă UTL subterană -->
            <path class="{peltier_class}" d="M 80 275 L 80 340 Q 80 355 95 355 L 365 355 Q 380 355 380 340 L 380 275" 
                  fill="none" stroke="{'#06d6a0' if peltier_on else '#334155'}" stroke-width="8" stroke-linecap="round"/>
            <text x="230" y="342" text-anchor="middle" fill="{'#06d6a0' if peltier_on else '#64748b'}" font-size="11" font-weight="bold">
                {'RĂCIRE PASIVĂ UTL ACTIVĂ (Sol: 12.8°C)' if peltier_on else 'Buclă UTL în Standby'}
            </text>

            <!-- Structura Turnului (Macheta Clădirii 3D) -->
            <rect x="110" y="25" width="240" height="250" rx="6" fill="url(#buildingGrad)" stroke="#334155" stroke-width="2"/>
            
            <!-- Ferestre etaje clădire -->
            <g fill="#334155" opacity="0.4">
                <rect x="130" y="45" width="35" height="22" rx="3"/>
                <rect x="180" y="45" width="35" height="22" rx="3"/>
                <rect x="245" y="45" width="35" height="22" rx="3"/>
                <rect x="295" y="45" width="35" height="22" rx="3"/>

                <rect x="130" y="85" width="35" height="22" rx="3"/>
                <rect x="180" y="85" width="35" height="22" rx="3"/>
                <rect x="245" y="85" width="35" height="22" rx="3"/>
                <rect x="295" y="85" width="35" height="22" rx="3"/>

                <rect x="130" y="125" width="35" height="22" rx="3"/>
                <rect x="180" y="125" width="35" height="22" rx="3"/>
                <rect x="245" y="125" width="35" height="22" rx="3"/>
                <rect x="295" y="125" width="35" height="22" rx="3"/>

                <rect x="130" y="165" width="35" height="22" rx="3"/>
                <rect x="180" y="165" width="35" height="22" rx="3"/>
                <rect x="245" y="165" width="35" height="22" rx="3"/>
                <rect x="295" y="165" width="35" height="22" rx="3"/>
            </g>

            <!-- Etichetă clădire -->
            <text x="230" y="40" text-anchor="middle" fill="#94a3b8" font-size="11" font-weight="700" letter-spacing="1">TURNUL GRAVITHERM (12-20 ETAJE)</text>

            <!-- Rezervor sus (apă recirculată) -->
            <rect x="160" y="55" width="140" height="28" rx="5" fill="#0369a1" stroke="#38bdf8" stroke-width="1.5"/>
            <text x="230" y="73" text-anchor="middle" fill="#ffffff" font-size="11" font-weight="bold">REZERVOR APĂ (12V DC)</text>

            <!-- Conducta verticală de cădere PPER -->
            <!-- Fundal conductă -->
            <rect x="184" y="83" width="12" height="150" fill="#0f172a" stroke="#1e293b" stroke-width="1"/>
            <!-- Flux de apă animat prin CSS -->
            <line class="{pipe_class}" x1="190" y1="83" x2="190" y2="233" 
                  stroke="url(#waterFlowGrad)" stroke-width="{'8' if pump_on else '2'}" opacity="{'1.0' if pump_on else '0.3'}"/>

            <!-- Turbină Hidro PPER (la baza coloanei) -->
            <circle cx="190" cy="240" r="18" fill="#1e293b" stroke="#38bdf8" stroke-width="2.5"/>
            <g class="{turbine_class}">
                <line x1="190" y1="225" x2="190" y2="255" stroke="#38bdf8" stroke-width="3"/>
                <line x1="175" y1="240" x2="205" y2="240" stroke="#38bdf8" stroke-width="3"/>
                <line x1="179" y1="229" x2="201" y2="251" stroke="#38bdf8" stroke-width="2.5"/>
                <line x1="179" y1="251" x2="201" y2="229" stroke="#38bdf8" stroke-width="2.5"/>
            </g>
            <circle cx="190" cy="240" r="5" fill="#f8fafc"/>

            <!-- Becul / LED-ul fizic cu strălucire (aprins la generare PPER) -->
            <g class="{led_class}" transform="translate(245, 222)">
                <circle cx="18" cy="18" r="14" fill="{'#facc15' if pump_on else '#475569'}" 
                        stroke="{'#fef08a' if pump_on else '#334155'}" stroke-width="2"/>
                <!-- Filament -->
                <path d="M 12 22 L 15 14 L 21 14 L 24 22" fill="none" stroke="{'#78350f' if pump_on else '#1e293b'}" stroke-width="1.5"/>
                <text x="18" y="38" text-anchor="middle" fill="{'#fef08a' if pump_on else '#64748b'}" font-size="9" font-weight="bold">
                    {'LED GENERATOR ON' if pump_on else 'LED OPRIT'}
                </text>
            </g>

            <!-- Fire legătură generator -> LED -->
            <path d="M 208 240 L 245 240" fill="none" stroke="{'#eab308' if pump_on else '#334155'}" stroke-width="2" stroke-dasharray="3 2"/>

            <!-- Casete Telemetrie Live lângă tub -->
            <!-- Presiune -->
            <g transform="translate(20, 100)">
                <rect width="85" height="42" rx="6" fill="#0f172a" stroke="#0284c7" stroke-width="1.5" opacity="0.95"/>
                <text x="8" y="16" fill="#7dd3fc" font-size="9" font-weight="600">PRESIUNE</text>
                <text x="8" y="34" fill="#f8fafc" font-size="14" font-weight="800" font-family="'JetBrains Mono', monospace">{press_val}</text>
            </g>

            <!-- Debit -->
            <g transform="translate(20, 155)">
                <rect width="85" height="42" rx="6" fill="#0f172a" stroke="#0284c7" stroke-width="1.5" opacity="0.95"/>
                <text x="8" y="16" fill="#7dd3fc" font-size="9" font-weight="600">DEBIT MACHETĂ</text>
                <text x="8" y="34" fill="#f8fafc" font-size="13" font-weight="800" font-family="'JetBrains Mono', monospace">{flow_val}</text>
            </g>

            <!-- Putere Extrapolată 60m clădire reală -->
            <g transform="translate(340, 100)">
                <rect width="105" height="52" rx="6" fill="#0f172a" stroke="#10b981" stroke-width="1.5" opacity="0.95"/>
                <text x="8" y="16" fill="#6ee7b7" font-size="9" font-weight="700">PPER CLĂDIRE (60m)</text>
                <text x="8" y="36" fill="#10b981" font-size="17" font-weight="800" font-family="'JetBrains Mono', monospace">{p_extrap}</text>
                <text x="8" y="47" fill="#94a3b8" font-size="8">Machetă: {p_lab}</text>
            </g>

            <!-- Stare Pompă badge -->
            <g transform="translate(340, 165)">
                <rect width="105" height="38" rx="6" fill="{'rgba(2, 132, 199, 0.25)' if pump_on else 'rgba(51, 65, 85, 0.25)'}" 
                      stroke="{'#0284c7' if pump_on else '#475569'}" stroke-width="1.5"/>
                <text x="52" y="16" text-anchor="middle" fill="#94a3b8" font-size="9" font-weight="600">POMPĂ QR50D</text>
                <text x="52" y="31" text-anchor="middle" fill="{'#38bdf8' if pump_on else '#64748b'}" font-size="12" font-weight="bold">
                    {'PORNITĂ (100%)' if pump_on else 'OPRITĂ'}
                </text>
            </g>
        </svg>
        """
        return html.Div(
            [dcc.Markdown(svg_content, dangerously_allow_html=True)],
            style={"width": "100%", "height": "320px", "display": "flex", "alignItems": "center"},
        )

    # Layout-ul complet
    app.layout = html.Div(
        [
            # Injectare stiluri CSS
            html.Div([dcc.Markdown(f"<style>{CUSTOM_CSS}</style>", dangerously_allow_html=True)]),
            # Componente ascunse pentru ascultarea tastelor din browser (clientside callback)
            dcc.Input(id="key-press-input", type="text", style={"display": "none"}),
            html.Div(id="clientside-listener-dummy", style={"display": "none"}),
            # Interval periodic 1 Hz
            dcc.Interval(id="demo-interval", interval=cfg.dashboard_interval_ms, n_intervals=0),
            # Container principal fără scroll la 1920x1080
            html.Div(
                [
                    # 1. BANDA DE SUS (Header)
                    html.Div(
                        [
                            # Stânga: Brand & Titlu
                            html.Div(
                                [
                                    html.H1(
                                        "GraviTherm",
                                        style={
                                            "fontSize": "26px",
                                            "fontWeight": "800",
                                            "color": "#38bdf8",
                                            "letterSpacing": "-0.5px",
                                            "display": "inline-block",
                                            "marginRight": "8px",
                                        },
                                    ),
                                    html.Span(
                                        "DEMO LIVE",
                                        style={
                                            "fontSize": "11px",
                                            "fontWeight": "800",
                                            "backgroundColor": "#0284c7",
                                            "color": "#ffffff",
                                            "padding": "3px 8px",
                                            "borderRadius": "6px",
                                            "verticalAlign": "middle",
                                            "letterSpacing": "0.5px",
                                        },
                                    ),
                                    html.Div(
                                        "TechChallenge Honeywell 2026 · Etapa II (Prototip Laborator)",
                                        style={"fontSize": "12px", "color": "#94a3b8", "marginTop": "2px"},
                                    ),
                                ],
                                style={"width": "28%"},
                            ),
                            # Centru: Ceas mare + Badge Fază
                            html.Div(
                                [
                                    html.Div(
                                        [
                                            html.Span(
                                                id="clock-display",
                                                children="00:00",
                                                className="mono-font",
                                                style={
                                                    "fontSize": "38px",
                                                    "fontWeight": "800",
                                                    "color": "#f8fafc",
                                                    "letterSpacing": "1px",
                                                    "marginRight": "14px",
                                                },
                                            ),
                                            html.Span(
                                                id="phase-badge",
                                                children="Faza 0 · Noapte",
                                                style={
                                                    "fontSize": "15px",
                                                    "fontWeight": "700",
                                                    "backgroundColor": "rgba(56, 189, 248, 0.15)",
                                                    "color": "#38bdf8",
                                                    "border": "1px solid rgba(56, 189, 248, 0.35)",
                                                    "padding": "6px 14px",
                                                    "borderRadius": "20px",
                                                    "verticalAlign": "middle",
                                                },
                                            ),
                                        ],
                                        style={
                                            "display": "flex",
                                            "alignItems": "center",
                                            "justifyContent": "center",
                                        },
                                    ),
                                    html.Div(
                                        id="waiting-for-space-msg",
                                        children="Faza curentă în desfășurare",
                                        style={
                                            "fontSize": "12px",
                                            "color": "#94a3b8",
                                            "marginTop": "2px",
                                            "fontWeight": "600",
                                        },
                                    ),
                                ],
                                style={"width": "44%", "textAlign": "center"},
                            ),
                            # Dreapta: LIVE, Status Pastile & Butoane discrete
                            html.Div(
                                [
                                    html.Div(
                                        [
                                            html.Span(className="live-dot"),
                                            html.Span(
                                                "LIVE",
                                                style={
                                                    "fontSize": "12px",
                                                    "fontWeight": "800",
                                                    "color": "#ef4444",
                                                    "marginRight": "10px",
                                                },
                                            ),
                                            # Pastilă Pompă
                                            html.Span(
                                                id="pill-pump",
                                                children="POMPĂ OFF",
                                                style={
                                                    "fontSize": "11px",
                                                    "fontWeight": "700",
                                                    "backgroundColor": "#1e293b",
                                                    "color": "#94a3b8",
                                                    "padding": "4px 8px",
                                                    "borderRadius": "6px",
                                                    "marginRight": "6px",
                                                },
                                            ),
                                            # Pastilă UTL
                                            html.Span(
                                                id="pill-utl",
                                                children="UTL ON",
                                                style={
                                                    "fontSize": "11px",
                                                    "fontWeight": "700",
                                                    "backgroundColor": "#064e3b",
                                                    "color": "#34d399",
                                                    "padding": "4px 8px",
                                                    "borderRadius": "6px",
                                                    "marginRight": "12px",
                                                },
                                            ),
                                        ],
                                        style={
                                            "display": "flex",
                                            "alignItems": "center",
                                            "justifyContent": "flex-end",
                                            "marginBottom": "6px",
                                        },
                                    ),
                                    # Butoane discrete backup
                                    html.Div(
                                        [
                                            html.Button(
                                                "Space → Următoarea",
                                                id="btn-next",
                                                className="btn-ctrl",
                                                style={"marginRight": "4px"},
                                            ),
                                            html.Button(
                                                "Pauză (P)",
                                                id="btn-pause",
                                                className="btn-ctrl",
                                                style={"marginRight": "4px"},
                                            ),
                                            html.Button(
                                                "Reset (R)",
                                                id="btn-reset",
                                                className="btn-ctrl",
                                                style={"marginRight": "4px"},
                                            ),
                                            html.Button(
                                                "STOP (S)",
                                                id="btn-stop",
                                                className="btn-ctrl btn-emergency",
                                            ),
                                        ],
                                        style={"display": "flex", "justifyContent": "flex-end"},
                                    ),
                                ],
                                style={"width": "28%"},
                            ),
                        ],
                        className="glass-card",
                        style={
                            "display": "flex",
                            "alignItems": "center",
                            "justifyContent": "space-between",
                            "marginBottom": "12px",
                            "padding": "10px 18px",
                        },
                    ),
                    # 2. RÂNDUL KPI (5 Carduri mari, fonturi >= 48px)
                    html.Div(
                        [
                            # Card 1: Decizia Agentului
                            html.Div(
                                [
                                    html.Div(
                                        "DECIZIA AGENTULUI RL",
                                        style={
                                            "fontSize": "11px",
                                            "fontWeight": "700",
                                            "color": "#94a3b8",
                                            "letterSpacing": "0.5px",
                                        },
                                    ),
                                    html.Div(
                                        id="kpi-decision-text",
                                        children="Pre-răcire UTL pe tarif ieftin",
                                        style={
                                            "fontSize": "20px",
                                            "fontWeight": "800",
                                            "color": "#38bdf8",
                                            "lineHeight": "1.25",
                                            "margin": "8px 0",
                                        },
                                    ),
                                    html.Div(
                                        id="kpi-decision-sub",
                                        children="Tarif: 0.45 lei/kWh · Minimizare rețea",
                                        style={"fontSize": "11px", "color": "#cbd5e1"},
                                    ),
                                ],
                                className="kpi-card",
                                style={"width": "26%"},
                            ),
                            # Card 2: Energie recuperată PPER (Wh)
                            html.Div(
                                [
                                    html.Div(
                                        "ENERGIE RECUPERATĂ PPER",
                                        style={
                                            "fontSize": "11px",
                                            "fontWeight": "700",
                                            "color": "#94a3b8",
                                            "letterSpacing": "0.5px",
                                        },
                                    ),
                                    html.Div(
                                        [
                                            html.Span(
                                                id="kpi-energy-pper",
                                                children="0.00",
                                                className="mono-font",
                                                style={
                                                    "fontSize": "48px",
                                                    "fontWeight": "800",
                                                    "color": "#38bdf8",
                                                    "lineHeight": "1",
                                                },
                                            ),
                                            html.Span(
                                                " Wh",
                                                style={
                                                    "fontSize": "18px",
                                                    "fontWeight": "700",
                                                    "color": "#7dd3fc",
                                                },
                                            ),
                                        ],
                                        style={"margin": "4px 0"},
                                    ),
                                    html.Div(
                                        id="kpi-energy-extrapolated",
                                        children="Extrapolat: 0.00 kWh/zi clădire",
                                        style={"fontSize": "11px", "color": "#94a3b8"},
                                    ),
                                ],
                                className="kpi-card",
                                style={"width": "18.5%"},
                            ),
                            # Card 3: Economie Energie (%)
                            html.Div(
                                [
                                    html.Div(
                                        "ECONOMIE ENERGIE VS. CLASIC",
                                        style={
                                            "fontSize": "11px",
                                            "fontWeight": "700",
                                            "color": "#94a3b8",
                                            "letterSpacing": "0.5px",
                                        },
                                    ),
                                    html.Div(
                                        [
                                            html.Span(
                                                id="kpi-energy-savings",
                                                children="14.2",
                                                className="mono-font",
                                                style={
                                                    "fontSize": "48px",
                                                    "fontWeight": "800",
                                                    "color": "#10b981",
                                                    "lineHeight": "1",
                                                },
                                            ),
                                            html.Span(
                                                " %",
                                                style={
                                                    "fontSize": "22px",
                                                    "fontWeight": "700",
                                                    "color": "#6ee7b7",
                                                },
                                            ),
                                        ],
                                        style={"margin": "4px 0"},
                                    ),
                                    html.Div(
                                        "Țintă Faza III: -10...18% consum",
                                        style={"fontSize": "11px", "color": "#94a3b8"},
                                    ),
                                ],
                                className="kpi-card",
                                style={"width": "18.5%"},
                            ),
                            # Card 4: Cost Economisit (lei)
                            html.Div(
                                [
                                    html.Div(
                                        "COST ECONOMISIT",
                                        style={
                                            "fontSize": "11px",
                                            "fontWeight": "700",
                                            "color": "#94a3b8",
                                            "letterSpacing": "0.5px",
                                        },
                                    ),
                                    html.Div(
                                        [
                                            html.Span(
                                                id="kpi-cost-saved",
                                                children="21.5",
                                                className="mono-font",
                                                style={
                                                    "fontSize": "48px",
                                                    "fontWeight": "800",
                                                    "color": "#f59e0b",
                                                    "lineHeight": "1",
                                                },
                                            ),
                                            html.Span(
                                                " lei",
                                                style={
                                                    "fontSize": "18px",
                                                    "fontWeight": "700",
                                                    "color": "#fcd34d",
                                                },
                                            ),
                                        ],
                                        style={"margin": "4px 0"},
                                    ),
                                    html.Div(
                                        id="kpi-cost-pct",
                                        children="Economie cost: 19.8%",
                                        style={"fontSize": "11px", "color": "#94a3b8"},
                                    ),
                                ],
                                className="kpi-card",
                                style={"width": "18.5%"},
                            ),
                            # Card 5: Confort Termic
                            html.Div(
                                [
                                    html.Div(
                                        "CONFORMITATE CONFORT (21-24°C)",
                                        style={
                                            "fontSize": "11px",
                                            "fontWeight": "700",
                                            "color": "#94a3b8",
                                            "letterSpacing": "0.5px",
                                        },
                                    ),
                                    html.Div(
                                        [
                                            html.Span(
                                                id="kpi-comfort-rl",
                                                children="100.0",
                                                className="mono-font",
                                                style={
                                                    "fontSize": "48px",
                                                    "fontWeight": "800",
                                                    "color": "#10b981",
                                                    "lineHeight": "1",
                                                },
                                            ),
                                            html.Span(
                                                " %",
                                                style={
                                                    "fontSize": "20px",
                                                    "fontWeight": "700",
                                                    "color": "#6ee7b7",
                                                },
                                            ),
                                        ],
                                        style={"margin": "4px 0"},
                                    ),
                                    html.Div(
                                        id="kpi-comfort-classic",
                                        children="Control clasic: 91.2%",
                                        style={"fontSize": "11px", "color": "#94a3b8"},
                                    ),
                                ],
                                className="kpi-card",
                                style={"width": "18.5%"},
                            ),
                        ],
                        style={
                            "display": "flex",
                            "justifyContent": "space-between",
                            "gap": "10px",
                            "marginBottom": "12px",
                        },
                    ),
                    # 3. RÂNDUL CENTRAL: Schema SVG Clădire (40%) + Grafic Presiune/PPER (60%)
                    html.Div(
                        [
                            # Stânga: Schema Animată a Clădirii
                            html.Div(
                                [
                                    html.Div(
                                        [
                                            html.Span(
                                                "SCHEMĂ MACHETĂ FIZICĂ · CIRCUITE ACTIVE",
                                                style={
                                                    "fontSize": "12px",
                                                    "fontWeight": "700",
                                                    "color": "#94a3b8",
                                                    "letterSpacing": "0.5px",
                                                },
                                            ),
                                        ],
                                        style={"marginBottom": "4px"},
                                    ),
                                    html.Div(id="building-svg-container", children=render_building_svg(None)),
                                ],
                                className="glass-card",
                                style={"width": "40%", "height": "350px"},
                            ),
                            # Dreapta: Grafic Presiune & Putere PPER & Energie
                            html.Div(
                                [
                                    dcc.Graph(
                                        id="graph-pressure-power",
                                        config={"displayModeBar": False, "responsive": True},
                                        style={"width": "100%", "height": "325px"},
                                    )
                                ],
                                className="glass-card",
                                style={"width": "60%", "height": "350px"},
                            ),
                        ],
                        style={
                            "display": "flex",
                            "justifyContent": "space-between",
                            "gap": "12px",
                            "marginBottom": "12px",
                        },
                    ),
                    # 4. RÂNDUL DE JOS (3 Grafice / Carduri)
                    html.Div(
                        [
                            # Grafic 1: Temperaturi (°C)
                            html.Div(
                                [
                                    dcc.Graph(
                                        id="graph-temperatures",
                                        config={"displayModeBar": False, "responsive": True},
                                        style={"width": "100%", "height": "260px"},
                                    )
                                ],
                                className="glass-card",
                                style={"width": "36%", "height": "285px"},
                            ),
                            # Grafic 2: Consum Rețea (kW) & Tarif
                            html.Div(
                                [
                                    dcc.Graph(
                                        id="graph-grid-power",
                                        config={"displayModeBar": False, "responsive": True},
                                        style={"width": "100%", "height": "260px"},
                                    )
                                ],
                                className="glass-card",
                                style={"width": "34%", "height": "285px"},
                            ),
                            # Card 3: Timeline Actuatori + Jurnal Decizii RL
                            html.Div(
                                [
                                    html.Div(
                                        "JURNAL DECIZII AGENT RL & ACTUATORI",
                                        style={
                                            "fontSize": "11px",
                                            "fontWeight": "700",
                                            "color": "#94a3b8",
                                            "letterSpacing": "0.5px",
                                            "marginBottom": "8px",
                                        },
                                    ),
                                    # Timeline simplificat
                                    html.Div(
                                        [
                                            html.Div(
                                                [
                                                    html.Span(
                                                        "POMPĂ PPER: ",
                                                        style={
                                                            "fontSize": "11px",
                                                            "fontWeight": "bold",
                                                            "color": "#94a3b8",
                                                        },
                                                    ),
                                                    html.Span(
                                                        id="timeline-pump-status",
                                                        children="OPRITĂ",
                                                        style={"fontSize": "12px", "fontWeight": "bold"},
                                                    ),
                                                ],
                                                style={"marginBottom": "4px"},
                                            ),
                                            html.Div(
                                                [
                                                    html.Span(
                                                        "PELTIER UTL: ",
                                                        style={
                                                            "fontSize": "11px",
                                                            "fontWeight": "bold",
                                                            "color": "#94a3b8",
                                                        },
                                                    ),
                                                    html.Span(
                                                        id="timeline-peltier-status",
                                                        children="PORNIT",
                                                        style={
                                                            "fontSize": "12px",
                                                            "fontWeight": "bold",
                                                            "color": "#34d399",
                                                        },
                                                    ),
                                                ],
                                                style={"marginBottom": "8px"},
                                            ),
                                        ]
                                    ),
                                    # Jurnal ultimele linii
                                    html.Div(
                                        id="decision-log-list",
                                        style={
                                            "backgroundColor": "rgba(7, 10, 19, 0.75)",
                                            "border": "1px solid rgba(255, 255, 255, 0.05)",
                                            "borderRadius": "8px",
                                            "padding": "8px 10px",
                                            "height": "170px",
                                            "overflowY": "hidden",
                                            "fontSize": "11px",
                                            "lineHeight": "1.5",
                                            "color": "#cbd5e1",
                                        },
                                    ),
                                ],
                                className="glass-card",
                                style={"width": "30%", "height": "285px"},
                            ),
                        ],
                        style={
                            "display": "flex",
                            "justifyContent": "space-between",
                            "gap": "12px",
                            "marginBottom": "8px",
                        },
                    ),
                    # 5. SUBZONA FOOTER
                    html.Div(
                        [
                            html.Span(
                                "Raspberry Pi 4 · ONNX Runtime · Inferență locală offline",
                                style={"fontWeight": "600", "color": "#64748b"},
                            ),
                            html.Span(
                                " · Comenzi rapide: [Space / →]: Faza următoare | [P]: Pauză | [R]: Reset | [S]: STOP URGENȚĂ",
                                style={"color": "#475569"},
                            ),
                            html.Span(
                                id="footer-phase-status",
                                children=" · Faza 0/5",
                                style={"float": "right", "fontWeight": "bold", "color": "#38bdf8"},
                            ),
                        ],
                        style={"fontSize": "11px", "color": "#64748b", "padding": "2px 6px"},
                    ),
                ],
                style={"maxWidth": "1840px", "margin": "0 auto", "padding": "12px 16px"},
            ),
            # 6. ECRAN DE SUMAR FINAL (FAZA 5 OVERLAY)
            html.Div(
                id="summary-overlay",
                children=[
                    html.Div(
                        [
                            html.H2(
                                "🏆 REZULTATE FINALE GRAVITHERM",
                                style={
                                    "fontSize": "30px",
                                    "fontWeight": "800",
                                    "color": "#38bdf8",
                                    "marginBottom": "4px",
                                    "textAlign": "center",
                                },
                            ),
                            html.P(
                                "Validat pe macheta de laborator · Scalabil la clădiri de birouri reale (Simulate-then-scale)",
                                style={
                                    "fontSize": "14px",
                                    "color": "#94a3b8",
                                    "textAlign": "center",
                                    "marginBottom": "24px",
                                },
                            ),
                            # Grilă metrici sumar
                            html.Div(
                                [
                                    # Card Sumar 1: PPER
                                    html.Div(
                                        [
                                            html.Div(
                                                "ENERGIE RECUPERATĂ PPER",
                                                style={
                                                    "fontSize": "12px",
                                                    "color": "#94a3b8",
                                                    "fontWeight": "700",
                                                },
                                            ),
                                            html.Div(
                                                id="summary-pper-val",
                                                children="2.4 Wh (machetă)",
                                                className="mono-font",
                                                style={
                                                    "fontSize": "32px",
                                                    "fontWeight": "800",
                                                    "color": "#38bdf8",
                                                    "margin": "8px 0",
                                                },
                                            ),
                                            html.Div(
                                                id="summary-pper-scale",
                                                children="Extrapolat: ~280 Wh/zi clădire 20 etaje",
                                                style={"fontSize": "12px", "color": "#cbd5e1"},
                                            ),
                                        ],
                                        style={
                                            "backgroundColor": "rgba(30, 41, 59, 0.8)",
                                            "padding": "18px",
                                            "borderRadius": "12px",
                                            "border": "1px solid rgba(255, 255, 255, 0.1)",
                                            "width": "31%",
                                        },
                                    ),
                                    # Card Sumar 2: Economie Energie & Cost
                                    html.Div(
                                        [
                                            html.Div(
                                                "ECONOMIE NETĂ TOTALĂ",
                                                style={
                                                    "fontSize": "12px",
                                                    "color": "#94a3b8",
                                                    "fontWeight": "700",
                                                },
                                            ),
                                            html.Div(
                                                id="summary-energy-pct",
                                                children="-14.2% kWh",
                                                className="mono-font",
                                                style={
                                                    "fontSize": "32px",
                                                    "fontWeight": "800",
                                                    "color": "#10b981",
                                                    "margin": "8px 0",
                                                },
                                            ),
                                            html.Div(
                                                id="summary-cost-pct",
                                                children="Economie cost: -20.4% lei",
                                                style={
                                                    "fontSize": "13px",
                                                    "fontWeight": "700",
                                                    "color": "#f59e0b",
                                                },
                                            ),
                                        ],
                                        style={
                                            "backgroundColor": "rgba(30, 41, 59, 0.8)",
                                            "padding": "18px",
                                            "borderRadius": "12px",
                                            "border": "1px solid rgba(255, 255, 255, 0.1)",
                                            "width": "31%",
                                        },
                                    ),
                                    # Card Sumar 3: Impact Mediu CO2
                                    html.Div(
                                        [
                                            html.Div(
                                                "IMPACT CLIMATIC (CO2 EVITAT)",
                                                style={
                                                    "fontSize": "12px",
                                                    "color": "#94a3b8",
                                                    "fontWeight": "700",
                                                },
                                            ),
                                            html.Div(
                                                id="summary-co2-val",
                                                children="1.840 kg CO2 / an",
                                                className="mono-font",
                                                style={
                                                    "fontSize": "30px",
                                                    "fontWeight": "800",
                                                    "color": "#34d399",
                                                    "margin": "8px 0",
                                                },
                                            ),
                                            html.Div(
                                                "Factor emisie România: 0.26 kg CO2/kWh",
                                                style={"fontSize": "12px", "color": "#cbd5e1"},
                                            ),
                                        ],
                                        style={
                                            "backgroundColor": "rgba(30, 41, 59, 0.8)",
                                            "padding": "18px",
                                            "borderRadius": "12px",
                                            "border": "1px solid rgba(255, 255, 255, 0.1)",
                                            "width": "31%",
                                        },
                                    ),
                                ],
                                style={
                                    "display": "flex",
                                    "justifyContent": "space-between",
                                    "marginBottom": "24px",
                                },
                            ),
                            # Butoane închidere overlay / reluare
                            html.Div(
                                [
                                    html.Button(
                                        "Închide Sumar (Reia Demo / Reset)",
                                        id="btn-close-summary",
                                        className="btn-ctrl",
                                        style={
                                            "fontSize": "14px",
                                            "padding": "10px 24px",
                                            "marginRight": "12px",
                                        },
                                    ),
                                ],
                                style={"textAlign": "center"},
                            ),
                        ],
                        style={
                            "backgroundColor": "#0b1120",
                            "border": "2px solid #38bdf8",
                            "borderRadius": "18px",
                            "maxWidth": "950px",
                            "width": "90%",
                            "padding": "32px",
                            "boxShadow": "0 25px 50px -12px rgba(0, 0, 0, 0.75)",
                        },
                    )
                ],
                style={
                    "display": "none",  # ascuns implicit, devine flex la Faza 5
                    "position": "fixed",
                    "top": "0",
                    "left": "0",
                    "width": "100vw",
                    "height": "100vh",
                    "backgroundColor": "rgba(3, 7, 18, 0.85)",
                    "backdropFilter": "blur(8px)",
                    "zIndex": "9999",
                    "alignItems": "center",
                    "justifyContent": "center",
                },
            ),
        ]
    )

    # Clientside Callback pentru ascultarea tastelor din fereastra de browser
    clientside_callback(
        """
        function(n_intervals) {
            if (!window._gravitherm_listener_installed) {
                window._gravitherm_listener_installed = true;
                window.addEventListener('keydown', function(event) {
                    var key = event.key;
                    if (key === ' ' || key === 'ArrowRight' || key === 'p' || key === 'P' || 
                        key === 'r' || key === 'R' || key === 's' || key === 'S') {
                        event.preventDefault();
                        var input = document.getElementById('key-press-input');
                        if (input) {
                            input.value = key + '_' + Date.now();
                            input.dispatchEvent(new Event('input', { bubbles: true }));
                        }
                    }
                });
            }
            return window.dash_clientside.no_update;
        }
        """,
        Output("clientside-listener-dummy", "children"),
        Input("demo-interval", "n_intervals"),
    )

    # Callback pentru tratarea comenzilor din tastatură și butoane UI
    @app.callback(
        Output("key-press-input", "value"),
        [
            Input("key-press-input", "value"),
            Input("btn-next", "n_clicks"),
            Input("btn-pause", "n_clicks"),
            Input("btn-reset", "n_clicks"),
            Input("btn-stop", "n_clicks"),
            Input("btn-close-summary", "n_clicks"),
        ],
        prevent_initial_call=True,
    )
    def handle_controls(
        key_value: str | None,
        btn_next: int | None,
        btn_pause: int | None,
        btn_reset: int | None,
        btn_stop: int | None,
        btn_close_sum: int | None,
    ) -> str:
        ctx = dash.callback_context
        if not ctx.triggered:
            return ""

        triggered_id = ctx.triggered[0]["prop_id"].split(".")[0]

        if triggered_id == "key-press-input" and key_value:
            key_code = key_value.split("_")[0]
            engine.handle_command_string(key_code)
        elif triggered_id == "btn-next":
            engine.next_phase()
        elif triggered_id == "btn-pause":
            engine.toggle_pause()
        elif triggered_id == "btn-reset" or triggered_id == "btn-close-summary":
            engine.reset()
        elif triggered_id == "btn-stop":
            engine.emergency_stop()

        return ""

    # Callback principal de actualizare periodică a UI-ului (1 Hz)
    @app.callback(
        [
            Output("clock-display", "children"),
            Output("phase-badge", "children"),
            Output("waiting-for-space-msg", "children"),
            Output("pill-pump", "children"),
            Output("pill-pump", "style"),
            Output("pill-utl", "children"),
            Output("pill-utl", "style"),
            Output("kpi-decision-text", "children"),
            Output("kpi-decision-sub", "children"),
            Output("kpi-energy-pper", "children"),
            Output("kpi-energy-extrapolated", "children"),
            Output("kpi-energy-savings", "children"),
            Output("kpi-cost-saved", "children"),
            Output("kpi-cost-pct", "children"),
            Output("kpi-comfort-rl", "children"),
            Output("kpi-comfort-classic", "children"),
            Output("timeline-pump-status", "children"),
            Output("timeline-pump-status", "style"),
            Output("timeline-peltier-status", "children"),
            Output("timeline-peltier-status", "style"),
            Output("decision-log-list", "children"),
            Output("footer-phase-status", "children"),
            Output("building-svg-container", "children"),
            Output("graph-pressure-power", "figure"),
            Output("graph-temperatures", "figure"),
            Output("graph-grid-power", "figure"),
            Output("summary-overlay", "style"),
            Output("summary-pper-val", "children"),
            Output("summary-pper-scale", "children"),
            Output("summary-energy-pct", "children"),
            Output("summary-cost-pct", "children"),
            Output("summary-co2-val", "children"),
        ],
        Input("demo-interval", "n_intervals"),
    )
    def update_dashboard_views(n_intervals: int) -> tuple[Any, ...]:
        status = engine.get_status_dict()
        history = list(data_model.history)
        last_pt: TelemetryPoint | None = history[-1] if history else None

        # 1. Ceas & Fază
        sim_h = float(status["sim_hour"])
        h_int = int(sim_h)
        m_int = int((sim_h - h_int) * 60)
        clock_str = f"{h_int:02d}:{m_int:02d}" if h_int < 24 else "24:00"
        phase_badge_str = status["phase_short"]

        if status["state"] == EngineState.PHASE_COMPLETED.value:
            waiting_msg = html.Span(
                "▶ Faza încheiată · Apasă Space pentru faza următoare",
                className="waiting-badge",
                style={"color": "#38bdf8", "fontWeight": "800"},
            )
        elif status["state"] == EngineState.PAUSED.value:
            waiting_msg = html.Span(
                "⏸ PAUZĂ (Apasă P pentru reluare)", style={"color": "#f59e0b", "fontWeight": "700"}
            )
        elif status["state"] == EngineState.EMERGENCY_STOPPED.value:
            waiting_msg = html.Span(
                "⛔ STOP DE URGENȚĂ ACTIV (Apasă R)", style={"color": "#ef4444", "fontWeight": "800"}
            )
        elif status["state"] == EngineState.FINISHED.value:
            waiting_msg = html.Span(
                "🏆 Demo completat · 24h simulate", style={"color": "#10b981", "fontWeight": "800"}
            )
        else:
            waiting_msg = (
                f"Faza în desfășurare ({status['phase_elapsed_s']:.0f}s / {status['phase_duration_s']:.0f}s)"
            )

        # 2. Pastile Actuatori
        pump_active = bool(status["pump_active"])
        peltier_active = bool(status["peltier_active"])

        if pump_active:
            pill_pump_text = "POMPĂ ON"
            pill_pump_style = {
                "fontSize": "11px",
                "fontWeight": "700",
                "backgroundColor": "#0369a1",
                "color": "#38bdf8",
                "padding": "4px 8px",
                "borderRadius": "6px",
                "marginRight": "6px",
            }
        else:
            pill_pump_text = "POMPĂ OFF"
            pill_pump_style = {
                "fontSize": "11px",
                "fontWeight": "700",
                "backgroundColor": "#1e293b",
                "color": "#94a3b8",
                "padding": "4px 8px",
                "borderRadius": "6px",
                "marginRight": "6px",
            }

        if peltier_active:
            pill_utl_text = "UTL ON"
            pill_utl_style = {
                "fontSize": "11px",
                "fontWeight": "700",
                "backgroundColor": "#064e3b",
                "color": "#34d399",
                "padding": "4px 8px",
                "borderRadius": "6px",
                "marginRight": "12px",
            }
        else:
            pill_utl_text = "UTL OFF"
            pill_utl_style = {
                "fontSize": "11px",
                "fontWeight": "700",
                "backgroundColor": "#1e293b",
                "color": "#94a3b8",
                "padding": "4px 8px",
                "borderRadius": "6px",
                "marginRight": "12px",
            }

        # 3. KPI-uri
        if last_pt:
            kpi_dec_text = last_pt.phase_decision
            if cfg.fixed_tariff_enabled:
                kpi_dec_sub = f"Tarif fix: {last_pt.tariff_lei_kwh:.2f} lei/kWh · Minimizare rețea"
            else:
                kpi_dec_sub = f"Tarif: {last_pt.tariff_lei_kwh:.2f} lei/kWh ({last_pt.tariff_zone})"
            kpi_energy_pper = f"{last_pt.energy_pper_wh:.2f}"
            kpi_energy_extrap = f"Extrapolat: {last_pt.energy_pper_real_kwh:.2f} kWh/zi"
            kpi_energy_savings = f"{last_pt.energy_savings_pct:.1f}"
            saved_lei = max(0.0, last_pt.cost_grid_classic_lei - last_pt.cost_grid_rl_lei)
            kpi_cost_saved = f"{saved_lei:.2f}"
            kpi_cost_pct = f"Economie cost: {last_pt.cost_savings_pct:.1f}%"
            kpi_comfort_rl = f"{last_pt.comfort_pct_rl:.1f}"
            kpi_comfort_classic = f"Control clasic: {last_pt.comfort_pct_classic:.1f}%"
        else:
            kpi_dec_text = status["phase_decision"]
            if cfg.fixed_tariff_enabled:
                kpi_dec_sub = f"Tarif fix: {cfg.fixed_tariff_lei_kwh:.2f} lei/kWh · Minimizare rețea"
            else:
                kpi_dec_sub = "Tarif: 0.45 lei/kWh (Noapte)"
            kpi_energy_pper = "0.00"
            kpi_energy_extrap = "Extrapolat: 0.00 kWh/zi"
            kpi_energy_savings = "0.0"
            kpi_cost_saved = "0.00"
            kpi_cost_pct = "Economie cost: 0.0%"
            kpi_comfort_rl = "100.0"
            kpi_comfort_classic = "Control clasic: 100.0%"

        # 4. Timeline text
        tl_pump_str = f"PORNITĂ ({status['pump_speed_pct']:.0f}%)" if pump_active else "OPRITĂ"
        tl_pump_col = (
            {"color": "#38bdf8", "fontSize": "12px", "fontWeight": "bold"}
            if pump_active
            else {
                "color": "#94a3b8",
                "fontSize": "12px",
                "fontWeight": "bold",
            }
        )
        tl_pelt_str = "PORNIT (Răcire UTL)" if peltier_active else "OPRIT"
        tl_pelt_col = (
            {"color": "#34d399", "fontSize": "12px", "fontWeight": "bold"}
            if peltier_active
            else {
                "color": "#94a3b8",
                "fontSize": "12px",
                "fontWeight": "bold",
            }
        )

        # 5. Jurnal Decizii
        recent_logs = list(data_model.decision_log)[-5:]
        log_elements = [
            html.Div(
                entry, style={"marginBottom": "6px", "borderBottom": "1px solid rgba(255, 255, 255, 0.05)"}
            )
            for entry in reversed(recent_logs)
        ]

        # 6. Footer status
        footer_status = f" · Faza {status['phase_id']}/5 ({status['phase_name']})"

        # 7. Schema SVG
        svg_div = render_building_svg(last_pt)

        # 8. Generare Grafice Plotly (Axa fixă 00:00 - 24:00, fără pâlpâit)
        hours_x = [pt.sim_hour for pt in history]

        # Template grafice dark
        layout_base = {
            "template": "plotly_dark",
            "paper_bgcolor": "rgba(0,0,0,0)",
            "plot_bgcolor": "rgba(15, 23, 42, 0.6)",
            "font": {"family": "Plus Jakarta Sans, sans-serif", "color": "#94a3b8", "size": 11},
            "margin": {"l": 45, "r": 35, "t": 35, "b": 35},
            "uirevision": "constant_demo_view",
        }

        # --- Grafic Central: Presiune Coloană (kPa) & Putere PPER (W) ---
        fig_pper = go.Figure()
        if history:
            fig_pper.add_trace(
                go.Scatter(
                    x=hours_x,
                    y=[pt.pressure_kpa for pt in history],
                    name="Presiune coloană (kPa)",
                    line={"color": "#0284c7", "width": 2.5},
                    yaxis="y1",
                )
            )
            fig_pper.add_trace(
                go.Scatter(
                    x=hours_x,
                    y=[pt.power_pper_extrapolated_w for pt in history],
                    name="Putere PPER extrapolat (W)",
                    line={"color": "#10b981", "width": 2},
                    yaxis="y2",
                )
            )
            fig_pper.add_trace(
                go.Scatter(
                    x=hours_x,
                    y=[pt.energy_pper_wh for pt in history],
                    name="Energie machetă cumulat (Wh)",
                    line={"color": "#f59e0b", "width": 1.5, "dash": "dot"},
                    yaxis="y1",
                )
            )

        fig_pper.update_layout(
            **layout_base,
            title={
                "text": "HIDRAULICĂ COLOANĂ & RECUPERARE ENERGIE PPER",
                "font": {"size": 12, "color": "#f8fafc"},
            },
            xaxis={
                "title": "Ora simulată (00:00 - 24:00)",
                "range": [0, 24],
                "dtick": 3,
                "gridcolor": "rgba(255,255,255,0.05)",
            },
            yaxis={"title": "Presiune (kPa) / Wh", "range": [0, 22], "gridcolor": "rgba(255,255,255,0.05)"},
            yaxis2={
                "title": "Putere clădire reală (W)",
                "overlaying": "y",
                "side": "right",
                "range": [0, 26],
                "showgrid": False,
            },
            legend={
                "orientation": "h",
                "yanchor": "bottom",
                "y": 1.02,
                "xanchor": "right",
                "x": 1,
                "font": {"size": 10},
            },
        )

        # --- Grafic Jos Stânga: Temperaturi (°C) ---
        fig_temp = go.Figure()

        # Bandă de confort termic 21-24°C umbrită verde
        fig_temp.add_hrect(
            y0=cfg.comfort_min_c,
            y1=cfg.comfort_max_c,
            fillcolor="rgba(16, 185, 129, 0.12)",
            line_width=1,
            line_color="rgba(16, 185, 129, 0.3)",
            annotation_text="Banda de confort (21-24°C)",
            annotation_position="bottom right",
            annotation_font={"size": 9, "color": "#34d399"},
        )

        if history:
            fig_temp.add_trace(
                go.Scatter(
                    x=hours_x,
                    y=[pt.temp_int_rl for pt in history],
                    name="Interior RL (GraviTherm)",
                    line={"color": "#10b981", "width": 2.5},
                )
            )
            fig_temp.add_trace(
                go.Scatter(
                    x=hours_x,
                    y=[pt.temp_int_classic for pt in history],
                    name="Interior Control clasic",
                    line={"color": "#94a3b8", "width": 2, "dash": "dash"},
                )
            )
            fig_temp.add_trace(
                go.Scatter(
                    x=hours_x,
                    y=[pt.temp_ext for pt in history],
                    name="Exterior (Caniculă)",
                    line={"color": "#f97316", "width": 1.5},
                )
            )
            fig_temp.add_trace(
                go.Scatter(
                    x=hours_x,
                    y=[pt.temp_utl_return for pt in history],
                    name="Retur buclă UTL",
                    line={"color": "#06d6a0", "width": 1.5, "dash": "dot"},
                )
            )

        fig_temp.update_layout(
            **layout_base,
            title={"text": "TEMPERATURI · RL vs. CONTROL CLASIC", "font": {"size": 12, "color": "#f8fafc"}},
            xaxis={"range": [0, 24], "dtick": 4, "gridcolor": "rgba(255,255,255,0.05)"},
            yaxis={"title": "°C", "range": [6, 36], "gridcolor": "rgba(255,255,255,0.05)"},
            legend={
                "orientation": "h",
                "yanchor": "bottom",
                "y": 1.02,
                "xanchor": "right",
                "x": 1,
                "font": {"size": 9},
            },
        )

        # --- Grafic Jos Mijloc: Consum Rețea (kW) & Benzi Tarif ---
        fig_grid = go.Figure()

        # Evidențiere bandă vârf (15:00 - 18:00)
        peak_annotation = (
            "VÂRF CERERE REȚEA (15:00 - 18:00)" if cfg.fixed_tariff_enabled else "VÂRF TARIF (1.70 lei)"
        )
        peak_fill = "rgba(56, 189, 248, 0.12)" if cfg.fixed_tariff_enabled else "rgba(239, 68, 68, 0.15)"
        peak_border = "rgba(56, 189, 248, 0.35)" if cfg.fixed_tariff_enabled else "rgba(239, 68, 68, 0.4)"
        peak_font_color = "#38bdf8" if cfg.fixed_tariff_enabled else "#f87171"

        fig_grid.add_vrect(
            x0=15.0,
            x1=18.0,
            fillcolor=peak_fill,
            line_width=1,
            line_color=peak_border,
            annotation_text=peak_annotation,
            annotation_position="top left",
            annotation_font={"size": 9, "color": peak_font_color},
        )

        if history:
            fig_grid.add_trace(
                go.Scatter(
                    x=hours_x,
                    y=[pt.grid_power_rl_kw for pt in history],
                    name="Consum net RL (kW)",
                    line={"color": "#10b981", "width": 2.5},
                )
            )
            fig_grid.add_trace(
                go.Scatter(
                    x=hours_x,
                    y=[pt.grid_power_classic_kw for pt in history],
                    name="Consum Chiller clasic (kW)",
                    line={"color": "#94a3b8", "width": 2, "dash": "dot"},
                )
            )

        grid_title = (
            "CONSUM REȚEA HVAC (kW) · TARIF FIX"
            if cfg.fixed_tariff_enabled
            else "CONSUM REȚEA HVAC (kW) & TARIF"
        )
        fig_grid.update_layout(
            **layout_base,
            title={"text": grid_title, "font": {"size": 12, "color": "#f8fafc"}},
            xaxis={"range": [0, 24], "dtick": 4, "gridcolor": "rgba(255,255,255,0.05)"},
            yaxis={"title": "kW import rețea", "range": [0, 14], "gridcolor": "rgba(255,255,255,0.05)"},
            legend={
                "orientation": "h",
                "yanchor": "bottom",
                "y": 1.02,
                "xanchor": "right",
                "x": 1,
                "font": {"size": 10},
            },
        )

        # 9. Verificare Sumar Final Faza 5 Overlay
        is_phase_5 = status["phase_id"] == 5
        summary_style: dict[str, str] = {
            "display": "flex" if is_phase_5 else "none",
            "position": "fixed",
            "top": "0",
            "left": "0",
            "width": "100vw",
            "height": "100vh",
            "backgroundColor": "rgba(3, 7, 18, 0.88)",
            "backdropFilter": "blur(8px)",
            "zIndex": "9999",
            "alignItems": "center",
            "justifyContent": "center",
        }

        sum_metrics = data_model.get_summary_metrics()
        sum_pper_val = f"{sum_metrics.get('energy_pper_lab_wh', 0.0):.2f} Wh (machetă)"
        sum_pper_scale = (
            f"Extrapolat: {sum_metrics.get('energy_pper_real_kwh_day', 0.0):.2f} kWh/zi (clădire 20 etaje)"
        )
        sum_energy_pct = f"-{sum_metrics.get('energy_savings_pct', 0.0):.1f}% kWh economisiți"
        sum_cost_pct = f"Economie cost: -{sum_metrics.get('cost_savings_pct', 0.0):.1f}% ({sum_metrics.get('cost_saved_lei_year', 0.0):,.0f} lei/an)"
        sum_co2_val = f"{sum_metrics.get('co2_avoided_kg_year', 0.0):.0f} kg CO2 / an"

        return (
            clock_str,
            phase_badge_str,
            waiting_msg,
            pill_pump_text,
            pill_pump_style,
            pill_utl_text,
            pill_utl_style,
            kpi_dec_text,
            kpi_dec_sub,
            kpi_energy_pper,
            kpi_energy_extrap,
            kpi_energy_savings,
            kpi_cost_saved,
            kpi_cost_pct,
            kpi_comfort_rl,
            kpi_comfort_classic,
            tl_pump_str,
            tl_pump_col,
            tl_pelt_str,
            tl_pelt_col,
            log_elements,
            footer_status,
            svg_div,
            fig_pper,
            fig_temp,
            fig_grid,
            summary_style,
            sum_pper_val,
            sum_pper_scale,
            sum_energy_pct,
            sum_cost_pct,
            sum_co2_val,
        )

    return app
