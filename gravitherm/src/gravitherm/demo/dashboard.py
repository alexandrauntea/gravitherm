"""Dashboard Plotly Dash pentru Demo Live GraviTherm (în limba română) - Versiunea 2.

Reîmprospătare vizuală:
- Temă luminoasă vibrantă (paleta oficială GraviTherm: #055b65, #45828b, #1bd488, #b2c9c5, #e0e5e9, #fbfcfc);
- Fără emoji nicăieri în interfață;
- Ceas digital mare în banda de sus: alb (#fbfcfc), bold, >= 64px, monospace/tabular;
- Panou nou complet „Deciziile agentului AI” (decizie curentă cu bară de încredere + istoric colorat pe tipuri de acțiune);
- Schema SVG ștearsă complet;
- Overlay sumar Faza 5 cu închidere discretă (X, Esc, backdrop click), păstrând graficele finale vizibile;
- Buton „Reia demo” separat cu popover de confirmare (fără alert() nativ).
"""

from __future__ import annotations

import logging
from typing import Any

import dash
import plotly.graph_objects as go
import plotly.io as pio
from dash import Input, Output, clientside_callback, dcc, html

from gravitherm.demo.data_model import DataModel, TelemetryPoint
from gravitherm.demo.demo_config import DemoConfig
from gravitherm.demo.engine import DemoEngine, EngineState

logger = logging.getLogger("gravitherm.demo.dashboard")

# --- Paleta oficială GraviTherm ---
PALETTE = {
    "deep": "#055b65",  # Culoare principală brand: top bar, titluri, linie RL
    "teal": "#45828b",  # Culoare secundară: UTL, subtitluri, contururi
    "green": "#1bd488",  # Accent vibrant: economii, PPER, punct LIVE
    "sage": "#b2c9c5",  # Control clasic (linia fantomă), grid, elemente inactive
    "mist": "#e0e5e9",  # Borduri, separatoare, fundal carduri
    "white": "#fbfcfc",  # Fundal pagină
    "card_bg": "#ffffff",  # Fundal carduri albe
    "coral": "#ef6f5e",  # Warning, stop de urgență, exterior canicular
    "yellow": "#f5b83d",  # Alertă tarif, pauză
}

# --- Template Plotly personalizat pentru GraviTherm ---
gt_template = go.layout.Template()
gt_template.layout = go.Layout(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font={
        "family": "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
        "color": PALETTE["deep"],
    },
    colorway=[PALETTE["deep"], PALETTE["green"], PALETTE["teal"], PALETTE["sage"]],
    xaxis={
        "automargin": True,
        "gridcolor": PALETTE["mist"],
        "linecolor": PALETTE["mist"],
        "zerolinecolor": PALETTE["mist"],
        "tickfont": {"color": PALETTE["teal"], "size": 10},
    },
    yaxis={
        "automargin": True,
        "title_standoff": 14,
        "gridcolor": PALETTE["mist"],
        "linecolor": PALETTE["mist"],
        "zerolinecolor": PALETTE["mist"],
        "tickfont": {"color": PALETTE["teal"], "size": 10},
    },
    yaxis2={
        "automargin": True,
        "title_standoff": 14,
        "tickfont": {"color": PALETTE["teal"], "size": 10},
    },
    legend={
        "orientation": "h",
        "yanchor": "bottom",
        "y": 1.02,
        "x": 0,
        "font": {"size": 10},
    },
)
pio.templates["gravitherm"] = gt_template


def configure_gt_figure(
    fig: go.Figure,
    margin_l: int = 55,
    margin_r: int = 25,
    margin_t: int = 40,
    margin_b: int = 30,
) -> None:
    """Aplică configurarea standard de layout Plotly GraviTherm:
    - Fără layout.title (titlurile sunt plasate ca anteturi HTML deasupra cardurilor);
    - Legendă orizontală deasupra zonei de plotare (yanchor=bottom, y=1.02, x=0);
    - automargin=True și title_standoff pe axele Y;
    - Margini generoase pentru a preveni trunchierea textelor și a valorilor numerice.
    """
    fig.update_layout(
        template="gravitherm",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin={"l": margin_l, "r": margin_r, "t": margin_t, "b": margin_b},
        hovermode="x unified",
        title=None,
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.02,
            "x": 0,
            "font": {"size": 10},
        },
    )
    fig.update_xaxes(automargin=True)
    fig.update_yaxes(automargin=True, title_standoff=14)

# Stiluri globale CSS injectate inline
CUSTOM_CSS = """
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700;800&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');

:root {
    --gt-deep: #055b65;
    --gt-teal: #45828b;
    --gt-green: #1bd488;
    --gt-sage: #b2c9c5;
    --gt-mist: #e0e5e9;
    --gt-white: #fbfcfc;
}

* {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
    font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
    -webkit-font-smoothing: antialiased;
}

html, body {
    background-color: var(--gt-white);
    color: var(--gt-deep);
    overflow-x: hidden;
    overflow-y: hidden;
    width: 100vw;
    height: 100vh;
}

.mono-font {
    font-family: 'JetBrains Mono', monospace;
    font-variant-numeric: tabular-nums;
}

@keyframes livePulse {
    0%, 100% { opacity: 1.0; transform: scale(1.0); }
    50% { opacity: 0.35; transform: scale(0.88); }
}

@keyframes pauseBlink {
    0%, 100% { opacity: 1.0; }
    50% { opacity: 0.25; }
}

@keyframes decisionPulse {
    0% { box-shadow: 0 0 0 0 rgba(27, 212, 136, 0.7); }
    70% { box-shadow: 0 0 0 10px rgba(27, 212, 136, 0); }
    100% { box-shadow: 0 0 0 0 rgba(27, 212, 136, 0); }
}

.live-dot {
    display: inline-block;
    width: 9px;
    height: 9px;
    background-color: var(--gt-green);
    border-radius: 50%;
    margin-right: 6px;
    box-shadow: 0 0 8px var(--gt-green);
    animation: livePulse 1.5s infinite;
}

.pause-badge-blink {
    animation: pauseBlink 1.2s infinite;
}

.decision-pulse {
    animation: decisionPulse 0.6s ease;
}

.top-bar {
    background-color: var(--gt-deep);
    color: var(--gt-white);
    border-bottom: 3px solid var(--gt-green);
    padding: 6px 18px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    box-shadow: 0 4px 12px rgba(5, 91, 101, 0.12);
}

.white-card {
    background: #ffffff;
    border: 1px solid var(--gt-mist);
    border-radius: 12px;
    box-shadow: 0 2px 8px rgba(5, 91, 101, 0.05);
    padding: 10px 14px;
}

.kpi-card {
    background: #ffffff;
    border: 1px solid var(--gt-mist);
    border-radius: 12px;
    box-shadow: 0 2px 8px rgba(5, 91, 101, 0.05);
    padding: 10px 14px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
}

.btn-ctrl {
    background: rgba(255, 255, 255, 0.12);
    border: 1px solid rgba(255, 255, 255, 0.25);
    color: var(--gt-white);
    border-radius: 7px;
    padding: 5px 11px;
    font-size: 12px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s ease;
}

.btn-ctrl:hover {
    background: rgba(255, 255, 255, 0.22);
    border-color: rgba(255, 255, 255, 0.45);
}

.btn-emergency {
    background: #ef6f5e;
    border: 1px solid #ef6f5e;
    color: #ffffff;
}

.btn-emergency:hover {
    background: #dc2626;
}

.btn-outline-primary {
    background: transparent;
    border: 2px solid var(--gt-deep);
    color: var(--gt-deep);
    border-radius: 8px;
    padding: 8px 20px;
    font-size: 13px;
    font-weight: 700;
    cursor: pointer;
    transition: all 0.2s ease;
}

.btn-outline-primary:hover {
    background: var(--gt-mist);
}

.btn-close-x {
    width: 32px;
    height: 32px;
    border-radius: 50%;
    border: none;
    background: var(--gt-mist);
    color: var(--gt-deep);
    font-size: 15px;
    font-weight: 800;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    transition: all 0.2s ease;
}

.btn-close-x:hover {
    background: var(--gt-sage);
    color: var(--gt-deep);
}

.custom-scroll::-webkit-scrollbar {
    width: 4px;
}
.custom-scroll::-webkit-scrollbar-track {
    background: var(--gt-white);
}
.custom-scroll::-webkit-scrollbar-thumb {
    background: var(--gt-sage);
    border-radius: 4px;
}
"""


def render_decision_history_item(rec: dict[str, Any]) -> html.Div:
    """Generează un rând stilizat pentru istoricul de decizii al agentului AI."""
    act_type = rec.get("action_type", "standby")
    chip_colors = {
        "pump": {
            "bg": "rgba(27, 212, 136, 0.18)",
            "border": PALETTE["green"],
            "text": PALETTE["deep"],
            "label": "POMPĂ",
        },
        "utl": {
            "bg": "rgba(69, 130, 139, 0.18)",
            "border": PALETTE["teal"],
            "text": PALETTE["deep"],
            "label": "UTL",
        },
        "standby": {
            "bg": "rgba(178, 201, 197, 0.28)",
            "border": PALETTE["sage"],
            "text": PALETTE["deep"],
            "label": "STANDBY",
        },
        "precool": {
            "bg": "rgba(5, 91, 101, 0.15)",
            "border": PALETTE["deep"],
            "text": PALETTE["deep"],
            "label": "PRE-RĂCIRE",
        },
    }
    cfg = chip_colors.get(act_type, chip_colors["standby"])

    return html.Div(
        [
            html.Span(
                rec.get("time_str", "00:00"),
                className="mono-font",
                style={
                    "fontSize": "11px",
                    "fontWeight": "800",
                    "color": PALETTE["deep"],
                    "marginRight": "8px",
                    "minWidth": "38px",
                },
            ),
            html.Span(
                cfg["label"],
                style={
                    "fontSize": "9px",
                    "fontWeight": "800",
                    "backgroundColor": cfg["bg"],
                    "border": f"1px solid {cfg['border']}",
                    "color": cfg["text"],
                    "padding": "2px 6px",
                    "borderRadius": "4px",
                    "marginRight": "8px",
                },
            ),
            html.Span(
                rec.get("action_text", ""),
                style={
                    "fontSize": "11px",
                    "color": PALETTE["deep"],
                    "flex": "1",
                    "whiteSpace": "nowrap",
                    "overflow": "hidden",
                    "textOverflow": "ellipsis",
                },
            ),
            html.Span(
                rec.get("gain_text", ""),
                className="mono-font",
                style={
                    "fontSize": "11px",
                    "fontWeight": "800",
                    "color": PALETTE["green"],
                    "marginLeft": "8px",
                    "whiteSpace": "nowrap",
                },
            ),
        ],
        style={
            "display": "flex",
            "alignItems": "center",
            "padding": "4px 8px",
            "borderRadius": "6px",
            "backgroundColor": "rgba(224, 229, 233, 0.4)",
            "border": "1px solid rgba(224, 229, 233, 0.8)",
        },
    )


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

    app.layout = html.Div(
        [
            # Injectare stiluri CSS
            html.Div([dcc.Markdown(f"<style>{CUSTOM_CSS}</style>", dangerously_allow_html=True)]),
            # Timer periodic Dash (1 Hz)
            dcc.Interval(id="demo-interval", interval=1000, n_intervals=0),
            # Input ascuns pentru recepte taste prin JS
            dcc.Input(id="key-press-input", type="text", style={"display": "none"}),
            html.Div(id="clientside-listener-dummy", style={"display": "none"}),
            # 1. BANDA DE SUS (Top Bar - solid #055b65 verde închis cu text alb)
            html.Div(
                [
                    # Stânga: Brand & Logo
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.Span(
                                        "GRAVITHERM",
                                        style={
                                            "fontSize": "20px",
                                            "fontWeight": "800",
                                            "color": "#fbfcfc",
                                            "letterSpacing": "1px",
                                        },
                                    ),
                                    html.Span(
                                        "Etapa II",
                                        style={
                                            "fontSize": "11px",
                                            "fontWeight": "800",
                                            "backgroundColor": PALETTE["green"],
                                            "color": PALETTE["deep"],
                                            "padding": "2px 8px",
                                            "borderRadius": "6px",
                                            "marginLeft": "8px",
                                            "verticalAlign": "middle",
                                            "letterSpacing": "0.5px",
                                        },
                                    ),
                                ],
                                style={"display": "flex", "alignItems": "center"},
                            ),
                            html.Div(
                                "TechChallenge Honeywell 2026 · Clădire Inteligentă",
                                style={"fontSize": "11px", "color": PALETTE["sage"], "marginTop": "2px"},
                            ),
                        ],
                        style={"flex": "0 0 250px"},
                    ),
                    # Centru: Ceas mare alb (>= 64px) + Badge Fază
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.Span(
                                        id="clock-display",
                                        children="00:00",
                                        className="mono-font",
                                        style={
                                            "fontSize": "64px",
                                            "fontWeight": "800",
                                            "color": "#fbfcfc",
                                            "letterSpacing": "2px",
                                            "lineHeight": "1",
                                            "marginRight": "14px",
                                        },
                                    ),
                                    html.Div(
                                        [
                                            html.Span(
                                                id="phase-badge",
                                                children="Faza 0 · Noapte",
                                                style={
                                                    "fontSize": "13px",
                                                    "fontWeight": "800",
                                                    "backgroundColor": PALETTE["green"],
                                                    "color": PALETTE["deep"],
                                                    "padding": "5px 14px",
                                                    "borderRadius": "18px",
                                                    "display": "inline-block",
                                                },
                                            ),
                                            html.Span(
                                                id="pause-badge",
                                                children="PAUZĂ",
                                                className="pause-badge-blink",
                                                style={
                                                    "fontSize": "12px",
                                                    "fontWeight": "800",
                                                    "backgroundColor": PALETTE["yellow"],
                                                    "color": PALETTE["deep"],
                                                    "padding": "4px 10px",
                                                    "borderRadius": "6px",
                                                    "marginLeft": "8px",
                                                    "display": "none",
                                                },
                                            ),
                                        ],
                                        style={"display": "flex", "alignItems": "center"},
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
                                    "fontSize": "11px",
                                    "color": PALETTE["sage"],
                                    "marginTop": "2px",
                                    "fontWeight": "600",
                                },
                            ),
                        ],
                        style={"flex": "1", "textAlign": "center", "minWidth": "320px"},
                    ),
                    # Dreapta: LIVE, Status Actuatori & Butoane Comandă
                    html.Div(
                        [
                            # Rând 1: Toast feedback acțiuni + LIVE dot + Pastile actuatori
                            html.Div(
                                [
                                    html.Span(
                                        id="action-toast",
                                        children="",
                                        style={
                                            "fontSize": "11px",
                                            "fontWeight": "800",
                                            "backgroundColor": "rgba(27, 212, 136, 0.22)",
                                            "border": f"1px solid {PALETTE['green']}",
                                            "color": "#fbfcfc",
                                            "padding": "3px 8px",
                                            "borderRadius": "4px",
                                            "marginRight": "10px",
                                            "display": "none",
                                            "letterSpacing": "0.3px",
                                        },
                                    ),
                                    html.Span(className="live-dot"),
                                    html.Span(
                                        "LIVE",
                                        style={
                                            "fontSize": "12px",
                                            "fontWeight": "800",
                                            "color": PALETTE["green"],
                                            "marginRight": "8px",
                                        },
                                    ),
                                    html.Span(
                                        id="pill-pump",
                                        children="POMPĂ OFF",
                                        style={
                                            "fontSize": "11px",
                                            "fontWeight": "700",
                                            "backgroundColor": "rgba(255,255,255,0.12)",
                                            "color": PALETTE["sage"],
                                            "padding": "3px 8px",
                                            "borderRadius": "6px",
                                            "marginRight": "6px",
                                        },
                                    ),
                                    html.Span(
                                        id="pill-utl",
                                        children="UTL ON",
                                        style={
                                            "fontSize": "11px",
                                            "fontWeight": "700",
                                            "backgroundColor": PALETTE["teal"],
                                            "color": "#ffffff",
                                            "padding": "3px 8px",
                                            "borderRadius": "6px",
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
                            # Rând 2: Butoane Comandă Rapide
                            html.Div(
                                [
                                    html.Button(
                                        "Space →",
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
                                        "Sumar (T)",
                                        id="btn-open-summary",
                                        className="btn-ctrl",
                                        style={"marginRight": "4px", "display": "none"},
                                    ),
                                    html.Button(
                                        "Reia demo",
                                        id="btn-top-replay",
                                        className="btn-ctrl",
                                        style={
                                            "marginRight": "4px",
                                            "display": "none",
                                            "backgroundColor": "rgba(27, 212, 136, 0.25)",
                                            "borderColor": PALETTE["green"],
                                            "color": "#ffffff",
                                        },
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
                                style={"display": "flex", "alignItems": "center", "justifyContent": "flex-end"},
                            ),
                        ],
                        style={"flex": "0 0 auto", "minWidth": "360px"},
                    ),
                ],
                className="top-bar",
                style={
                    "backgroundColor": PALETTE["deep"],
                    "color": "#fbfcfc",
                    "borderBottom": f"3px solid {PALETTE['green']}",
                    "padding": "6px 20px",
                    "display": "flex",
                    "alignItems": "center",
                    "justifyContent": "space-between",
                    "boxShadow": "0 4px 14px rgba(5, 91, 101, 0.25)",
                    "width": "100%",
                },
            ),
            # CONTAINER PRINCIPAL
            html.Div(
                [
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
                                            "color": PALETTE["teal"],
                                            "letterSpacing": "0.5px",
                                        },
                                    ),
                                    html.Div(
                                        id="kpi-decision-text",
                                        children="Pre-răcire UTL pe tarif fix",
                                        style={
                                            "fontSize": "18px",
                                            "fontWeight": "800",
                                            "color": PALETTE["deep"],
                                            "lineHeight": "1.25",
                                            "margin": "6px 0",
                                        },
                                    ),
                                    html.Div(
                                        id="kpi-decision-sub",
                                        children="Tarif fix: 1.00 lei/kWh · Minimizare rețea",
                                        style={"fontSize": "11px", "color": PALETTE["teal"]},
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
                                            "color": PALETTE["teal"],
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
                                                    "color": PALETTE["green"],
                                                    "lineHeight": "1",
                                                },
                                            ),
                                            html.Span(
                                                " Wh",
                                                style={
                                                    "fontSize": "18px",
                                                    "fontWeight": "700",
                                                    "color": PALETTE["teal"],
                                                },
                                            ),
                                        ],
                                        style={"margin": "4px 0"},
                                    ),
                                    html.Div(
                                        id="kpi-energy-extrapolated",
                                        children="Extrapolat: 0.00 kWh/zi clădire 60m",
                                        style={"fontSize": "11px", "color": PALETTE["teal"]},
                                    ),
                                ],
                                className="kpi-card",
                                style={"width": "18.5%"},
                            ),
                            # Card 3: Economie Energie HVAC (%)
                            html.Div(
                                [
                                    html.Div(
                                        "ECONOMIE ENERGIE HVAC",
                                        style={
                                            "fontSize": "11px",
                                            "fontWeight": "700",
                                            "color": PALETTE["teal"],
                                            "letterSpacing": "0.5px",
                                        },
                                    ),
                                    html.Div(
                                        [
                                            html.Span(
                                                id="kpi-energy-savings",
                                                children="13.7",
                                                className="mono-font",
                                                style={
                                                    "fontSize": "48px",
                                                    "fontWeight": "800",
                                                    "color": PALETTE["green"],
                                                    "lineHeight": "1",
                                                },
                                            ),
                                            html.Span(
                                                " %",
                                                style={
                                                    "fontSize": "20px",
                                                    "fontWeight": "700",
                                                    "color": PALETTE["teal"],
                                                },
                                            ),
                                        ],
                                        style={"margin": "4px 0"},
                                    ),
                                    html.Div(
                                        "vs. Chiller mecanic clasic",
                                        style={"fontSize": "11px", "color": PALETTE["teal"]},
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
                                            "color": PALETTE["teal"],
                                            "letterSpacing": "0.5px",
                                        },
                                    ),
                                    html.Div(
                                        [
                                            html.Span(
                                                id="kpi-cost-saved",
                                                children="0.00",
                                                className="mono-font",
                                                style={
                                                    "fontSize": "48px",
                                                    "fontWeight": "800",
                                                    "color": PALETTE["deep"],
                                                    "lineHeight": "1",
                                                },
                                            ),
                                            html.Span(
                                                " lei",
                                                style={
                                                    "fontSize": "18px",
                                                    "fontWeight": "700",
                                                    "color": PALETTE["teal"],
                                                },
                                            ),
                                        ],
                                        style={"margin": "4px 0"},
                                    ),
                                    html.Div(
                                        id="kpi-cost-pct",
                                        children="Economie cost: 13.7%",
                                        style={"fontSize": "11px", "color": PALETTE["teal"]},
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
                                            "color": PALETTE["teal"],
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
                                                    "color": PALETTE["green"],
                                                    "lineHeight": "1",
                                                },
                                            ),
                                            html.Span(
                                                " %",
                                                style={
                                                    "fontSize": "20px",
                                                    "fontWeight": "700",
                                                    "color": PALETTE["teal"],
                                                },
                                            ),
                                        ],
                                        style={"margin": "4px 0"},
                                    ),
                                    html.Div(
                                        id="kpi-comfort-classic",
                                        children="Control clasic: 91.2%",
                                        style={"fontSize": "11px", "color": PALETTE["teal"]},
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
                            "marginBottom": "8px",
                        },
                    ),
                    # 3. RÂNDUL CENTRAL: Panoul Deciziile Agentului AI (38%) + Grafic Presiune/PPER (62%)
                    html.Div(
                        [
                            # Stânga: Panoul Deciziile Agentului AI
                            html.Div(
                                id="agent-decisions-panel",
                                children=[
                                    html.Div(
                                        [
                                            html.Span(
                                                "Deciziile agentului AI",
                                                style={
                                                    "fontSize": "13px",
                                                    "fontWeight": "800",
                                                    "color": PALETTE["deep"],
                                                    "letterSpacing": "0.3px",
                                                },
                                            ),
                                            html.Span(
                                                " · RLAEA · PPO · inferență ONNX locală",
                                                style={
                                                    "fontSize": "11px",
                                                    "fontWeight": "600",
                                                    "color": PALETTE["teal"],
                                                },
                                            ),
                                        ],
                                        style={"marginBottom": "8px"},
                                    ),
                                    # Card mare decizie curentă
                                    html.Div(
                                        id="agent-current-decision-card",
                                        children=[
                                            html.Div(
                                                id="agent-decision-action",
                                                children="PRE-RĂCIRE UTL · Pompă oprită",
                                                style={
                                                    "fontSize": "14px",
                                                    "fontWeight": "800",
                                                    "color": "#fbfcfc",
                                                    "lineHeight": "1.3",
                                                    "marginBottom": "3px",
                                                },
                                            ),
                                            html.Div(
                                                id="agent-decision-reason",
                                                children="tarif fix (1.00 lei) · stocare termică pasivă · T interior 21.8°C",
                                                style={
                                                    "fontSize": "11px",
                                                    "color": PALETTE["sage"],
                                                    "marginBottom": "8px",
                                                },
                                            ),
                                            html.Div(
                                                [
                                                    html.Div(
                                                        [
                                                            html.Span(
                                                                "Încredere decizie: ",
                                                                style={
                                                                    "fontSize": "10px",
                                                                    "color": PALETTE["mist"],
                                                                },
                                                            ),
                                                            html.Span(
                                                                id="agent-decision-confidence-val",
                                                                children="94%",
                                                                className="mono-font",
                                                                style={
                                                                    "fontSize": "11px",
                                                                    "fontWeight": "800",
                                                                    "color": PALETTE["green"],
                                                                },
                                                            ),
                                                        ],
                                                        style={"marginBottom": "3px"},
                                                    ),
                                                    html.Div(
                                                        html.Div(
                                                            id="agent-decision-confidence-bar",
                                                            style={
                                                                "width": "94%",
                                                                "height": "100%",
                                                                "backgroundColor": PALETTE["green"],
                                                                "borderRadius": "3px",
                                                                "transition": "width 0.4s ease",
                                                            },
                                                        ),
                                                        style={
                                                            "width": "100%",
                                                            "height": "5px",
                                                            "backgroundColor": "rgba(255, 255, 255, 0.15)",
                                                            "borderRadius": "3px",
                                                            "overflow": "hidden",
                                                        },
                                                    ),
                                                ]
                                            ),
                                        ],
                                        style={
                                            "backgroundColor": PALETTE["deep"],
                                            "color": "#fbfcfc",
                                            "borderLeft": f"6px solid {PALETTE['green']}",
                                            "borderRadius": "8px",
                                            "padding": "10px 14px",
                                            "marginBottom": "8px",
                                            "boxShadow": "0 4px 10px rgba(5, 91, 101, 0.15)",
                                        },
                                    ),
                                    # Istoric decizii
                                    html.Div(
                                        [
                                            html.Div(
                                                "ISTORIC DECIZII RECENTE",
                                                style={
                                                    "fontSize": "10px",
                                                    "fontWeight": "700",
                                                    "color": PALETTE["teal"],
                                                    "letterSpacing": "0.5px",
                                                    "marginBottom": "6px",
                                                },
                                            ),
                                            html.Div(
                                                id="agent-decision-history-list",
                                                className="custom-scroll",
                                                style={
                                                    "maxHeight": "175px",
                                                    "overflowY": "auto",
                                                    "display": "flex",
                                                    "flexDirection": "column",
                                                    "gap": "5px",
                                                },
                                            ),
                                        ]
                                    ),
                                ],
                                className="white-card",
                                style={
                                    "width": "38%",
                                    "height": "340px",
                                    "display": "flex",
                                    "flexDirection": "column",
                                    "justifyContent": "space-between",
                                },
                            ),
                            # Dreapta: Grafic Presiune & Putere PPER & Energie
                            html.Div(
                                [
                                    html.Div(
                                        "HIDRAULICĂ COLOANĂ & RECUPERARE ENERGIE PPER",
                                        style={
                                            "fontSize": "11px",
                                            "fontWeight": "800",
                                            "color": PALETTE["deep"],
                                            "letterSpacing": "0.5px",
                                            "marginBottom": "4px",
                                        },
                                    ),
                                    dcc.Graph(
                                        id="graph-pressure-power",
                                        config={"displayModeBar": False, "responsive": True},
                                        style={"width": "100%", "height": "295px"},
                                    ),
                                ],
                                className="white-card",
                                style={"width": "62%", "height": "340px"},
                            ),
                        ],
                        style={
                            "display": "flex",
                            "justifyContent": "space-between",
                            "gap": "10px",
                            "marginBottom": "8px",
                        },
                    ),
                    # 4. RÂNDUL DE JOS (Temperaturi, Consum Rețea, Stare Actuatori)
                    html.Div(
                        [
                            # Grafic 1: Temperaturi (°C)
                            html.Div(
                                [
                                    html.Div(
                                        "TEMPERATURI · RL vs. CONTROL CLASIC",
                                        style={
                                            "fontSize": "11px",
                                            "fontWeight": "800",
                                            "color": PALETTE["deep"],
                                            "letterSpacing": "0.5px",
                                            "marginBottom": "4px",
                                        },
                                    ),
                                    dcc.Graph(
                                        id="graph-temperatures",
                                        config={"displayModeBar": False, "responsive": True},
                                        style={"width": "100%", "height": "210px"},
                                    ),
                                ],
                                className="white-card",
                                style={"width": "35%", "height": "255px"},
                            ),
                            # Grafic 2: Consum Rețea (kW) & Tarif
                            html.Div(
                                [
                                    html.Div(
                                        "CONSUM REȚEA HVAC (kW) · TARIF FIX"
                                        if cfg.fixed_tariff_enabled
                                        else "CONSUM REȚEA HVAC (kW) & TARIF",
                                        style={
                                            "fontSize": "11px",
                                            "fontWeight": "800",
                                            "color": PALETTE["deep"],
                                            "letterSpacing": "0.5px",
                                            "marginBottom": "4px",
                                        },
                                    ),
                                    dcc.Graph(
                                        id="graph-grid-power",
                                        config={"displayModeBar": False, "responsive": True},
                                        style={"width": "100%", "height": "210px"},
                                    ),
                                ],
                                className="white-card",
                                style={"width": "35%", "height": "255px"},
                            ),
                            # Card 3: Stare Actuatori & Siguranță Hardware
                            html.Div(
                                [
                                    html.Div(
                                        "STARE ACTUATORI & SISTEM",
                                        style={
                                            "fontSize": "11px",
                                            "fontWeight": "800",
                                            "color": PALETTE["deep"],
                                            "letterSpacing": "0.5px",
                                            "marginBottom": "8px",
                                        },
                                    ),
                                    html.Div(
                                        [
                                            html.Div(
                                                [
                                                    html.Span(
                                                        "Pompă PPER: ",
                                                        style={
                                                            "fontSize": "11px",
                                                            "fontWeight": "700",
                                                            "color": PALETTE["teal"],
                                                        },
                                                    ),
                                                    html.Span(
                                                        id="timeline-pump-status",
                                                        children="OPRITĂ",
                                                        style={"fontSize": "12px", "fontWeight": "800"},
                                                    ),
                                                ],
                                                style={
                                                    "marginBottom": "6px",
                                                    "display": "flex",
                                                    "justifyContent": "space-between",
                                                },
                                            ),
                                            html.Div(
                                                [
                                                    html.Span(
                                                        "Peltier UTL: ",
                                                        style={
                                                            "fontSize": "11px",
                                                            "fontWeight": "700",
                                                            "color": PALETTE["teal"],
                                                        },
                                                    ),
                                                    html.Span(
                                                        id="timeline-peltier-status",
                                                        children="PORNIT",
                                                        style={"fontSize": "12px", "fontWeight": "800"},
                                                    ),
                                                ],
                                                style={
                                                    "marginBottom": "8px",
                                                    "display": "flex",
                                                    "justifyContent": "space-between",
                                                },
                                            ),
                                            html.Div(
                                                [
                                                    html.Span(
                                                        "Controler AI: ",
                                                        style={
                                                            "fontSize": "11px",
                                                            "fontWeight": "700",
                                                            "color": PALETTE["teal"],
                                                        },
                                                    ),
                                                    html.Span(
                                                        "PPO / ONNX (activ)",
                                                        style={
                                                            "fontSize": "11px",
                                                            "fontWeight": "700",
                                                            "color": PALETTE["deep"],
                                                        },
                                                    ),
                                                ],
                                                style={
                                                    "marginBottom": "6px",
                                                    "display": "flex",
                                                    "justifyContent": "space-between",
                                                },
                                            ),
                                            html.Div(
                                                [
                                                    html.Span(
                                                        "Siguranță: ",
                                                        style={
                                                            "fontSize": "11px",
                                                            "fontWeight": "700",
                                                            "color": PALETTE["teal"],
                                                        },
                                                    ),
                                                    html.Span(
                                                        "Watchdog 3.0s · Max 60°C",
                                                        style={
                                                            "fontSize": "11px",
                                                            "fontWeight": "700",
                                                            "color": PALETTE["green"],
                                                        },
                                                    ),
                                                ],
                                                style={
                                                    "marginBottom": "6px",
                                                    "display": "flex",
                                                    "justifyContent": "space-between",
                                                },
                                            ),
                                            html.Div(
                                                [
                                                    html.Span(
                                                        "Hardware RPi: ",
                                                        style={
                                                            "fontSize": "11px",
                                                            "fontWeight": "700",
                                                            "color": PALETTE["teal"],
                                                        },
                                                    ),
                                                    html.Span(
                                                        "GPIO 23/24, GPIO 25",
                                                        style={"fontSize": "11px", "color": PALETTE["teal"]},
                                                    ),
                                                ],
                                                style={"display": "flex", "justifyContent": "space-between"},
                                            ),
                                        ],
                                        style={
                                            "backgroundColor": "rgba(224, 229, 233, 0.4)",
                                            "border": f"1px solid {PALETTE['mist']}",
                                            "borderRadius": "8px",
                                            "padding": "10px 12px",
                                        },
                                    ),
                                ],
                                className="white-card",
                                style={"width": "30%", "height": "255px"},
                            ),
                        ],
                        style={
                            "display": "flex",
                            "justifyContent": "space-between",
                            "gap": "10px",
                            "marginBottom": "6px",
                        },
                    ),
                    # 5. FOOTER
                    html.Div(
                        [
                            html.Span(
                                "Raspberry Pi 4 · ONNX Runtime · Inferență locală offline",
                                style={"fontWeight": "600", "color": PALETTE["teal"]},
                            ),
                            html.Span(
                                " · Comenzi rapide: [Space / →]: Faza următoare | [P]: Pauză | [R]: Reset | [S]: STOP URGENȚĂ | [T]: Sumar",
                                style={"color": PALETTE["teal"]},
                            ),
                            html.Span(
                                id="footer-phase-status",
                                children=" · Faza 0/5",
                                style={"float": "right", "fontWeight": "bold", "color": PALETTE["deep"]},
                            ),
                        ],
                        style={"fontSize": "11px", "color": PALETTE["teal"], "padding": "2px 4px"},
                    ),
                ],
                style={"maxWidth": "1860px", "margin": "0 auto", "padding": "8px 16px"},
            ),
            # 6. OVERLAY SUMAR FAZA 5
            html.Div(
                id="summary-overlay",
                children=[
                    html.Div(
                        id="summary-modal-card",
                        children=[
                            # Buton X închidere
                            html.Button(
                                "X",
                                id="btn-close-summary-x",
                                className="btn-close-x",
                                style={"position": "absolute", "top": "16px", "right": "18px"},
                            ),
                            html.H2(
                                "Rezumatul zilei",
                                style={
                                    "fontSize": "28px",
                                    "fontWeight": "800",
                                    "color": PALETTE["deep"],
                                    "marginBottom": "4px",
                                    "textAlign": "center",
                                },
                            ),
                            html.P(
                                "Validat pe machetă · scalabil la clădiri reale (simulate-then-scale)",
                                style={
                                    "fontSize": "13px",
                                    "fontWeight": "600",
                                    "color": PALETTE["teal"],
                                    "textAlign": "center",
                                    "marginBottom": "24px",
                                },
                            ),
                            # 3 Carduri Mari
                            html.Div(
                                [
                                    # Card 1: PPER
                                    html.Div(
                                        [
                                            html.Div(
                                                "ENERGIE RECUPERATĂ PPER",
                                                style={
                                                    "fontSize": "11px",
                                                    "color": PALETTE["teal"],
                                                    "fontWeight": "700",
                                                },
                                            ),
                                            html.Div(
                                                id="summary-pper-val",
                                                children="0.60 Wh (machetă)",
                                                className="mono-font",
                                                style={
                                                    "fontSize": "30px",
                                                    "fontWeight": "800",
                                                    "color": PALETTE["deep"],
                                                    "margin": "8px 0",
                                                },
                                            ),
                                            html.Div(
                                                id="summary-pper-scale",
                                                children="Extrapolat: 0.21 kWh/zi (clădire 20 etaje)",
                                                style={"fontSize": "11px", "color": PALETTE["teal"]},
                                            ),
                                        ],
                                        style={
                                            "backgroundColor": "rgba(224, 229, 233, 0.45)",
                                            "border": f"1px solid {PALETTE['mist']}",
                                            "padding": "16px",
                                            "borderRadius": "10px",
                                            "width": "31%",
                                        },
                                    ),
                                    # Card 2: Economie
                                    html.Div(
                                        [
                                            html.Div(
                                                "ECONOMIE NETĂ TOTALĂ",
                                                style={
                                                    "fontSize": "11px",
                                                    "color": PALETTE["teal"],
                                                    "fontWeight": "700",
                                                },
                                            ),
                                            html.Div(
                                                id="summary-energy-pct",
                                                children="-13.7% kWh",
                                                className="mono-font",
                                                style={
                                                    "fontSize": "30px",
                                                    "fontWeight": "800",
                                                    "color": PALETTE["green"],
                                                    "margin": "8px 0",
                                                },
                                            ),
                                            html.Div(
                                                id="summary-cost-pct",
                                                children="Economie cost: -13.7%",
                                                style={
                                                    "fontSize": "12px",
                                                    "fontWeight": "700",
                                                    "color": PALETTE["deep"],
                                                },
                                            ),
                                        ],
                                        style={
                                            "backgroundColor": "rgba(27, 212, 136, 0.1)",
                                            "border": f"1px solid {PALETTE['green']}",
                                            "padding": "16px",
                                            "borderRadius": "10px",
                                            "width": "31%",
                                        },
                                    ),
                                    # Card 3: CO2
                                    html.Div(
                                        [
                                            html.Div(
                                                "IMPACT CLIMATIC (CO2 EVITAT)",
                                                style={
                                                    "fontSize": "11px",
                                                    "color": PALETTE["teal"],
                                                    "fontWeight": "700",
                                                },
                                            ),
                                            html.Div(
                                                id="summary-co2-val",
                                                children="1.840 kg CO2 / an",
                                                className="mono-font",
                                                style={
                                                    "fontSize": "28px",
                                                    "fontWeight": "800",
                                                    "color": PALETTE["deep"],
                                                    "margin": "8px 0",
                                                },
                                            ),
                                            html.Div(
                                                "Factor emisie România: 0.26 kg CO2/kWh",
                                                style={"fontSize": "11px", "color": PALETTE["teal"]},
                                            ),
                                        ],
                                        style={
                                            "backgroundColor": "rgba(224, 229, 233, 0.45)",
                                            "border": f"1px solid {PALETTE['mist']}",
                                            "padding": "16px",
                                            "borderRadius": "10px",
                                            "width": "31%",
                                        },
                                    ),
                                ],
                                style={
                                    "display": "flex",
                                    "justifyContent": "space-between",
                                    "marginBottom": "28px",
                                },
                            ),
                            # Butoane jos
                            html.Div(
                                [
                                    html.Button(
                                        "Reia demo",
                                        id="btn-overlay-replay",
                                        className="btn-outline-primary",
                                    ),
                                    html.Button(
                                        "Închide și vezi graficele zilei",
                                        id="btn-close-summary",
                                        style={
                                            "backgroundColor": PALETTE["deep"],
                                            "color": "#fbfcfc",
                                            "border": "none",
                                            "borderRadius": "8px",
                                            "padding": "10px 22px",
                                            "fontSize": "13px",
                                            "fontWeight": "700",
                                            "cursor": "pointer",
                                        },
                                    ),
                                ],
                                style={
                                    "display": "flex",
                                    "justifyContent": "space-between",
                                    "alignItems": "center",
                                },
                            ),
                        ],
                        style={
                            "backgroundColor": "#ffffff",
                            "border": f"2px solid {PALETTE['deep']}",
                            "borderRadius": "16px",
                            "maxWidth": "860px",
                            "width": "90%",
                            "padding": "32px 36px",
                            "position": "relative",
                            "boxShadow": "0 25px 50px rgba(5, 91, 101, 0.25)",
                        },
                    )
                ],
                style={
                    "display": "none",
                    "position": "fixed",
                    "top": "0",
                    "left": "0",
                    "width": "100vw",
                    "height": "100vh",
                    "backgroundColor": "rgba(5, 91, 101, 0.45)",
                    "backdropFilter": "blur(8px)",
                    "zIndex": "9999",
                    "alignItems": "center",
                    "justifyContent": "center",
                },
            ),
            # 7. POPOVER CONFIRMARE REIA DEMO
            html.Div(
                id="reset-confirm-popover",
                children=[
                    html.Div(
                        [
                            html.Div(
                                "Confirmare reluare",
                                style={
                                    "fontSize": "11px",
                                    "fontWeight": "700",
                                    "color": PALETTE["teal"],
                                    "marginBottom": "4px",
                                },
                            ),
                            html.Div(
                                "Sigur reiei demo-ul de la Faza 0?",
                                style={
                                    "fontSize": "15px",
                                    "fontWeight": "800",
                                    "color": PALETTE["deep"],
                                    "marginBottom": "16px",
                                },
                            ),
                            html.Div(
                                [
                                    html.Button(
                                        "Da, reia",
                                        id="btn-confirm-reset-yes",
                                        style={
                                            "backgroundColor": PALETTE["deep"],
                                            "color": "#ffffff",
                                            "border": "none",
                                            "borderRadius": "6px",
                                            "padding": "7px 16px",
                                            "fontWeight": "700",
                                            "cursor": "pointer",
                                            "marginRight": "10px",
                                            "fontSize": "13px",
                                        },
                                    ),
                                    html.Button(
                                        "Nu, anulează",
                                        id="btn-confirm-reset-no",
                                        style={
                                            "backgroundColor": PALETTE["mist"],
                                            "color": PALETTE["deep"],
                                            "border": "none",
                                            "borderRadius": "6px",
                                            "padding": "7px 16px",
                                            "fontWeight": "700",
                                            "cursor": "pointer",
                                            "fontSize": "13px",
                                        },
                                    ),
                                ],
                                style={"display": "flex", "justifyContent": "flex-end"},
                            ),
                        ],
                        style={
                            "backgroundColor": "#ffffff",
                            "border": f"2px solid {PALETTE['deep']}",
                            "borderRadius": "12px",
                            "padding": "18px 22px",
                            "boxShadow": "0 20px 50px rgba(5, 91, 101, 0.3)",
                            "maxWidth": "340px",
                            "width": "90%",
                        },
                    )
                ],
                style={
                    "display": "none",
                    "position": "fixed",
                    "top": "0",
                    "left": "0",
                    "width": "100vw",
                    "height": "100vh",
                    "backgroundColor": "rgba(5, 91, 101, 0.3)",
                    "backdropFilter": "blur(4px)",
                    "zIndex": "10010",
                    "alignItems": "center",
                    "justifyContent": "center",
                },
            ),
        ]
    )

    # Clientside Callback pentru ascultarea tastelor și click-ului pe backdrop
    clientside_callback(
        """
        function(n_intervals) {
            if (!window._gravitherm_listener_installed) {
                window._gravitherm_listener_installed = true;

                // Ascultare evenimente tastatură globală
                window.addEventListener('keydown', function(event) {
                    var activeEl = document.activeElement;
                    var activeTag = activeEl ? activeEl.tagName.toLowerCase() : '';
                    if (activeTag === 'input' || activeTag === 'textarea' || (activeEl && activeEl.isContentEditable)) {
                        return;
                    }

                    var key = event.key;
                    var isActionKey = (
                        key === ' ' || key === 'Spacebar' || key === 'ArrowRight' ||
                        key === 'p' || key === 'P' || 
                        key === 'r' || key === 'R' || 
                        key === 's' || key === 'S' ||
                        key === 'Escape' || 
                        key === 't' || key === 'T'
                    );

                    if (isActionKey) {
                        // Previne derularea paginii pe Space sau săgeți
                        if (key === ' ' || key === 'Spacebar' || key === 'ArrowRight') {
                            event.preventDefault();
                        }

                        // Declanșare prin click direct pe buton pentru animație și traseu nativ Dash
                        var btnId = null;
                        if (key === ' ' || key === 'Spacebar' || key === 'ArrowRight') {
                            btnId = 'btn-next';
                        } else if (key === 'p' || key === 'P') {
                            btnId = 'btn-pause';
                        } else if (key === 'r' || key === 'R') {
                            btnId = 'btn-reset';
                        } else if (key === 's' || key === 'S') {
                            btnId = 'btn-stop';
                        } else if (key === 'Escape') {
                            btnId = 'btn-close-summary-x';
                        } else if (key === 't' || key === 'T') {
                            btnId = 'btn-open-summary';
                        }

                        if (btnId) {
                            var btn = document.getElementById(btnId);
                            if (btn) {
                                btn.click();
                                return;
                            }
                        }

                        // Fallback pe input prin prototype setter React
                        var input = document.getElementById('key-press-input');
                        if (input) {
                            var nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                            if (nativeSetter) {
                                nativeSetter.call(input, key + '_' + Date.now());
                            } else {
                                input.value = key + '_' + Date.now();
                            }
                            input.dispatchEvent(new Event('input', { bubbles: true }));
                        }
                    }
                });

                // Click pe fundalul overlay-ului pentru închidere
                document.addEventListener('click', function(event) {
                    if (event.target && event.target.id === 'summary-overlay') {
                        var btnClose = document.getElementById('btn-close-summary-x');
                        if (btnClose) {
                            btnClose.click();
                        }
                    }
                });
            }
            return "";
        }
        """,
        Output("clientside-listener-dummy", "children"),
        Input("demo-interval", "n_intervals"),
    )

    # Callback pentru tratarea comenzilor hardware/engine din tastatură și butoane UI
    @app.callback(
        Output("key-press-input", "value"),
        [
            Input("key-press-input", "value"),
            Input("btn-next", "n_clicks"),
            Input("btn-pause", "n_clicks"),
            Input("btn-reset", "n_clicks"),
            Input("btn-stop", "n_clicks"),
            Input("btn-close-summary-x", "n_clicks"),
            Input("btn-close-summary", "n_clicks"),
            Input("btn-open-summary", "n_clicks"),
            Input("btn-overlay-replay", "n_clicks"),
            Input("btn-top-replay", "n_clicks"),
            Input("btn-confirm-reset-yes", "n_clicks"),
            Input("btn-confirm-reset-no", "n_clicks"),
        ],
        prevent_initial_call=True,
    )
    def handle_controls(
        key_value: str | None,
        btn_next: int | None,
        btn_pause: int | None,
        btn_reset: int | None,
        btn_stop: int | None,
        btn_close_x: int | None,
        btn_close_sum: int | None,
        btn_open_sum: int | None,
        btn_overlay_replay: int | None,
        btn_top_replay: int | None,
        btn_confirm_yes: int | None,
        btn_confirm_no: int | None,
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
        elif triggered_id == "btn-reset":
            engine.reset()
        elif triggered_id == "btn-stop":
            engine.emergency_stop()
        elif triggered_id in ("btn-close-summary-x", "btn-close-summary"):
            engine.close_summary()
        elif triggered_id == "btn-open-summary":
            engine.open_summary()
        elif triggered_id in ("btn-overlay-replay", "btn-top-replay"):
            engine.request_reset_confirm()
        elif triggered_id == "btn-confirm-reset-yes":
            engine.reset()
        elif triggered_id == "btn-confirm-reset-no":
            engine.cancel_reset_confirm()

        return ""

    # Callback principal de actualizare periodică a UI-ului (1 Hz)
    @app.callback(
        [
            Output("clock-display", "children"),
            Output("phase-badge", "children"),
            Output("pause-badge", "style"),
            Output("waiting-for-space-msg", "children"),
            Output("pill-pump", "children"),
            Output("pill-pump", "style"),
            Output("pill-utl", "children"),
            Output("pill-utl", "style"),
            Output("btn-open-summary", "style"),
            Output("btn-top-replay", "style"),
            Output("btn-pause", "children"),
            Output("btn-pause", "style"),
            Output("btn-stop", "style"),
            Output("action-toast", "children"),
            Output("action-toast", "style"),
            Output("kpi-decision-text", "children"),
            Output("kpi-decision-sub", "children"),
            Output("kpi-energy-pper", "children"),
            Output("kpi-energy-extrapolated", "children"),
            Output("kpi-energy-savings", "children"),
            Output("kpi-cost-saved", "children"),
            Output("kpi-cost-pct", "children"),
            Output("kpi-comfort-rl", "children"),
            Output("kpi-comfort-classic", "children"),
            Output("agent-decision-action", "children"),
            Output("agent-decision-reason", "children"),
            Output("agent-decision-confidence-val", "children"),
            Output("agent-decision-confidence-bar", "style"),
            Output("agent-decision-history-list", "children"),
            Output("timeline-pump-status", "children"),
            Output("timeline-pump-status", "style"),
            Output("timeline-peltier-status", "children"),
            Output("timeline-peltier-status", "style"),
            Output("footer-phase-status", "children"),
            Output("graph-pressure-power", "figure"),
            Output("graph-temperatures", "figure"),
            Output("graph-grid-power", "figure"),
            Output("summary-overlay", "style"),
            Output("reset-confirm-popover", "style"),
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

        # 1. Formatare ceas & badge fază în mod garantat sigur
        sim_h = float(status.get("sim_hour", 0.0))
        h_int = int(sim_h)
        m_int = int((sim_h - h_int) * 60)
        clock_str = status.get("sim_time_str") or (f"{h_int:02d}:{m_int:02d}" if h_int < 24 else "24:00")
        phase_badge_str = f"Faza {status.get('phase_id', 0)} · {status.get('phase_name', '')}"
        modal_open = bool(status.get("summary_modal_open", False))
        confirm_open = bool(status.get("reset_confirm_open", False))

        # Indicator Pauză (afișat lângă ceas) & Buton Pauză text/stil
        is_paused = bool(status.get("is_paused", status.get("state") == EngineState.PAUSED.value))
        pause_badge_style = {
            "fontSize": "12px",
            "fontWeight": "800",
            "backgroundColor": PALETTE["yellow"],
            "color": PALETTE["deep"],
            "padding": "4px 10px",
            "borderRadius": "6px",
            "marginLeft": "8px",
            "display": "inline-block" if is_paused else "none",
        }
        btn_pause_text = "Reia (P)" if is_paused else "Pauză (P)"
        btn_pause_style = {
            "marginRight": "4px",
            "backgroundColor": PALETTE["yellow"] if is_paused else "rgba(255, 255, 255, 0.12)",
            "color": PALETTE["deep"] if is_paused else "#ffffff",
            "borderColor": PALETTE["yellow"] if is_paused else "rgba(255, 255, 255, 0.25)",
            "fontWeight": "800" if is_paused else "600",
        }

        # Buton STOP (S) stil când este declanșat
        is_emergency = bool(
            status.get("is_emergency", status.get("state") == EngineState.EMERGENCY_STOPPED.value)
        )
        btn_stop_style = {
            "backgroundColor": "#b91c1c" if is_emergency else "#ef6f5e",
            "borderColor": "#b91c1c" if is_emergency else "#ef6f5e",
            "color": "#ffffff",
            "fontWeight": "800",
            "boxShadow": "0 0 12px rgba(239, 111, 94, 0.7)" if is_emergency else "none",
        }

        # Toast feedback acțiune (1-2s)
        toast_msg = str(status.get("last_action_msg", ""))
        action_toast_style = {
            "fontSize": "11px",
            "fontWeight": "800",
            "backgroundColor": "rgba(27, 212, 136, 0.22)",
            "border": f"1px solid {PALETTE['green']}",
            "color": "#fbfcfc",
            "padding": "3px 8px",
            "borderRadius": "4px",
            "marginRight": "10px",
            "display": "inline-block" if toast_msg else "none",
            "letterSpacing": "0.3px",
        }

        # Mesaj navigare
        waiting_for_next = bool(
            status.get("waiting_for_next", status.get("state") == EngineState.PHASE_COMPLETED.value)
        )
        wall_elapsed = float(status.get("wall_elapsed_s", status.get("phase_elapsed_s", 0.0)))
        phase_id = status.get("phase_id", 0)
        if waiting_for_next:
            if phase_id < 5:
                waiting_msg = "Fază încheiată · Apasă Space pentru faza următoare"
            else:
                waiting_msg = "Demo finalizat · 24h simulate"
        else:
            waiting_msg = f"Faza {phase_id} în desfășurare ({wall_elapsed:.0f}s)"

        # 2. Pastile Status Actuatori Top-Right
        if is_emergency:
            pump_active = False
            pelt_active = False
            pump_speed = 0.0
        else:
            pump_active = bool(status.get("actual_pump_on", status.get("pump_active", False)))
            pelt_active = bool(status.get("actual_peltier_on", status.get("peltier_active", False)))
            pump_speed = float(status.get("pump_speed_pct", 0.0))

        pill_pump_text = f"POMPĂ ON ({pump_speed:.0f}%)" if pump_active else "POMPĂ OFF"
        if pump_active:
            pill_pump_style = {
                "fontSize": "11px",
                "fontWeight": "800",
                "backgroundColor": PALETTE["green"],
                "color": PALETTE["deep"],
                "padding": "3px 8px",
                "borderRadius": "6px",
                "marginRight": "6px",
            }
        else:
            pill_pump_style = {
                "fontSize": "11px",
                "fontWeight": "700",
                "backgroundColor": "rgba(255,255,255,0.12)",
                "color": PALETTE["sage"],
                "padding": "3px 8px",
                "borderRadius": "6px",
                "marginRight": "6px",
            }

        pill_utl_text = "UTL ON" if pelt_active else "UTL OFF"
        if pelt_active:
            pill_utl_style = {
                "fontSize": "11px",
                "fontWeight": "800",
                "backgroundColor": PALETTE["teal"],
                "color": "#ffffff",
                "padding": "3px 8px",
                "borderRadius": "6px",
            }
        else:
            pill_utl_style = {
                "fontSize": "11px",
                "fontWeight": "700",
                "backgroundColor": "rgba(255,255,255,0.12)",
                "color": PALETTE["sage"],
                "padding": "3px 8px",
                "borderRadius": "6px",
            }

        # Vizibilitate butoane Sumar și Reia demo în top bar
        is_phase_5 = status.get("phase_id", 0) == 5
        btn_open_sum_style = {
            "marginRight": "4px",
            "display": "inline-block" if (is_phase_5 and not modal_open) else "none",
            "backgroundColor": PALETTE["teal"],
            "borderColor": PALETTE["teal"],
        }
        btn_top_replay_style = {
            "marginRight": "4px",
            "display": "inline-block" if (is_phase_5 and not modal_open) else "none",
            "backgroundColor": "rgba(27, 212, 136, 0.25)",
            "borderColor": PALETTE["green"],
            "color": "#ffffff",
        }

        # 3. KPI-uri (Rândul 2)
        if last_pt:
            kpi_dec_text = last_pt.phase_decision
            if cfg.fixed_tariff_enabled:
                kpi_dec_sub = f"Tarif fix: {last_pt.tariff_lei_kwh:.2f} lei/kWh · Minimizare rețea"
            else:
                kpi_dec_sub = f"Tarif: {last_pt.tariff_lei_kwh:.2f} lei/kWh ({last_pt.tariff_zone})"
            kpi_energy_pper = f"{last_pt.energy_pper_wh:.2f}"
            kpi_energy_extrap = f"Extrapolat: {last_pt.energy_pper_real_kwh:.2f} kWh/zi clădire 60m"
            kpi_energy_savings = f"{last_pt.energy_savings_pct:.1f}"
            saved_lei = max(0.0, last_pt.cost_grid_classic_lei - last_pt.cost_grid_rl_lei)
            kpi_cost_saved = f"{saved_lei:.2f}"
            kpi_cost_pct = f"Economie cost: {last_pt.cost_savings_pct:.1f}%"
            kpi_comfort_rl = f"{last_pt.comfort_pct_rl:.1f}"
            kpi_comfort_classic = f"Control clasic: {last_pt.comfort_pct_classic:.1f}%"
        else:
            kpi_dec_text = status.get("phase_decision", "Pre-răcire UTL pe tarif fix")
            if cfg.fixed_tariff_enabled:
                kpi_dec_sub = f"Tarif fix: {cfg.fixed_tariff_lei_kwh:.2f} lei/kWh · Minimizare rețea"
            else:
                kpi_dec_sub = "Tarif: 0.45 lei/kWh (Noapte)"
            kpi_energy_pper = "0.00"
            kpi_energy_extrap = "Extrapolat: 0.00 kWh/zi clădire 60m"
            kpi_energy_savings = "0.0"
            kpi_cost_saved = "0.00"
            kpi_cost_pct = "Economie cost: 0.0%"
            kpi_comfort_rl = "100.0"
            kpi_comfort_classic = "Control clasic: 100.0%"

        # 4. Panoul Deciziile Agentului AI (Rândul Central Stânga)
        curr_decision = data_model.get_current_decision()
        agent_dec_action = curr_decision.get("action_text", "STANDBY")
        agent_dec_reason = curr_decision.get("reason", "stare nominală sistem")
        conf_pct = int(curr_decision.get("confidence_pct", 95))
        agent_dec_conf_val = f"{conf_pct}%"
        agent_dec_conf_bar_style = {
            "width": f"{conf_pct}%",
            "height": "100%",
            "backgroundColor": PALETTE["green"],
            "borderRadius": "3px",
            "transition": "width 0.4s ease",
        }

        # Istoric decizii
        recent_decs = data_model.get_recent_decisions(limit=8)
        agent_dec_history_elements = [render_decision_history_item(rec) for rec in recent_decs]

        # 5. Stare Actuatori (Rândul de Jos Dreapta)
        tl_pump_str = f"PORNITĂ ({pump_speed:.0f}%)" if pump_active else "OPRITĂ"
        tl_pump_col = (
            {"color": PALETTE["green"], "fontSize": "12px", "fontWeight": "800"}
            if pump_active
            else {"color": PALETTE["teal"], "fontSize": "12px", "fontWeight": "700"}
        )

        tl_pelt_str = "PORNIT" if pelt_active else "OPRIT"
        tl_pelt_col = (
            {"color": PALETTE["deep"], "fontSize": "12px", "fontWeight": "800"}
            if pelt_active
            else {"color": PALETTE["teal"], "fontSize": "12px", "fontWeight": "700"}
        )

        # 6. Footer Status
        footer_status = f" · Faza {status.get('phase_id', 0)}/5 · {status.get('phase_name', '')}"

        # 7. Grafice Plotly (Temă luminoasă GraviTherm cu titluri HTML externe)
        hours_x = [pt.sim_hour for pt in history] if history else []

        # --- Grafic Central Dreapta: Presiune & Putere PPER ---
        fig_pper = go.Figure()
        if history:
            fig_pper.add_trace(
                go.Scatter(
                    x=hours_x,
                    y=[pt.pressure_kpa for pt in history],
                    name="Presiune coloană (kPa)",
                    line={"color": PALETTE["teal"], "width": 2},
                    yaxis="y1",
                )
            )
            fig_pper.add_trace(
                go.Scatter(
                    x=hours_x,
                    y=[pt.power_pper_extrapolated_w for pt in history],
                    name="Putere PPER clădire reală (W)",
                    line={"color": PALETTE["green"], "width": 3},
                    fill="tozeroy",
                    fillcolor="rgba(27, 212, 136, 0.15)",
                    yaxis="y2",
                )
            )
            fig_pper.add_trace(
                go.Scatter(
                    x=hours_x,
                    y=[pt.energy_pper_wh for pt in history],
                    name="Energie machetă cumulat (Wh)",
                    line={"color": PALETTE["deep"], "width": 1.5, "dash": "dot"},
                    yaxis="y1",
                )
            )

        fig_pper.update_layout(
            xaxis={
                "title": "Ora simulată (00:00 - 24:00)",
                "range": [0, 24],
                "dtick": 3,
                "gridcolor": PALETTE["mist"],
                "tickfont": {"size": 10, "color": PALETTE["teal"]},
            },
            yaxis={
                "title": "Presiune (kPa) / Wh",
                "range": [0, 22],
                "gridcolor": PALETTE["mist"],
                "tickfont": {"size": 10, "color": PALETTE["teal"]},
            },
            yaxis2={
                "title": "Putere clădire reală (W)",
                "overlaying": "y",
                "side": "right",
                "range": [0, 26],
                "showgrid": False,
                "tickfont": {"size": 10, "color": PALETTE["teal"]},
            },
        )
        configure_gt_figure(fig_pper, margin_l=60, margin_r=65, margin_t=40, margin_b=32)

        # --- Grafic Jos Stânga: Temperaturi (°C) ---
        fig_temp = go.Figure()

        # Bandă de confort termic 21-24°C umbrită verde pastel
        fig_temp.add_hrect(
            y0=cfg.comfort_min_c,
            y1=cfg.comfort_max_c,
            fillcolor="rgba(27, 212, 136, 0.08)",
            line_width=1,
            line_color="rgba(27, 212, 136, 0.35)",
            annotation_text="Banda de confort (21-24°C)",
            annotation_position="bottom right",
            annotation_font={"size": 9, "color": PALETTE["deep"]},
        )

        if history:
            fig_temp.add_trace(
                go.Scatter(
                    x=hours_x,
                    y=[pt.temp_int_rl for pt in history],
                    name="Interior RL (GraviTherm)",
                    line={"color": PALETTE["deep"], "width": 3},
                )
            )
            fig_temp.add_trace(
                go.Scatter(
                    x=hours_x,
                    y=[pt.temp_int_classic for pt in history],
                    name="Interior Control clasic",
                    line={"color": PALETTE["sage"], "width": 2, "dash": "dot"},
                )
            )
            fig_temp.add_trace(
                go.Scatter(
                    x=hours_x,
                    y=[pt.temp_ext for pt in history],
                    name="Exterior (Caniculă)",
                    line={"color": PALETTE["coral"], "width": 1.5},
                )
            )
            fig_temp.add_trace(
                go.Scatter(
                    x=hours_x,
                    y=[pt.temp_utl_return for pt in history],
                    name="Retur buclă UTL",
                    line={"color": PALETTE["teal"], "width": 1.5, "dash": "dash"},
                )
            )

        fig_temp.update_layout(
            xaxis={
                "range": [0, 24],
                "dtick": 4,
                "gridcolor": PALETTE["mist"],
                "tickfont": {"size": 10, "color": PALETTE["teal"]},
            },
            yaxis={
                "title": "°C",
                "range": [6, 36],
                "gridcolor": PALETTE["mist"],
                "tickfont": {"size": 10, "color": PALETTE["teal"]},
            },
        )
        configure_gt_figure(fig_temp, margin_l=50, margin_r=25, margin_t=40, margin_b=30)

        # --- Grafic Jos Mijloc: Consum Rețea (kW) & Benzi Tarif ---
        fig_grid = go.Figure()

        # Evidențiere bandă vârf cerere (15:00 - 18:00) cu tentă gălbuie/coral discretă
        fig_grid.add_vrect(
            x0=15.0,
            x1=18.0,
            fillcolor="rgba(245, 184, 61, 0.15)",
            line_width=1,
            line_color="rgba(245, 184, 61, 0.4)",
            annotation_text="VÂRF CERERE REȚEA (15:00 - 18:00)",
            annotation_position="top left",
            annotation_font={"size": 9, "color": PALETTE["deep"]},
        )

        if history:
            fig_grid.add_trace(
                go.Scatter(
                    x=hours_x,
                    y=[pt.grid_power_rl_kw for pt in history],
                    name="Consum net RL (kW)",
                    line={"color": PALETTE["deep"], "width": 3},
                )
            )
            fig_grid.add_trace(
                go.Scatter(
                    x=hours_x,
                    y=[pt.grid_power_classic_kw for pt in history],
                    name="Consum Chiller clasic (kW)",
                    line={"color": PALETTE["sage"], "width": 2, "dash": "dot"},
                )
            )

        fig_grid.update_layout(
            xaxis={
                "range": [0, 24],
                "dtick": 4,
                "gridcolor": PALETTE["mist"],
                "tickfont": {"size": 10, "color": PALETTE["teal"]},
            },
            yaxis={
                "title": "kW import rețea",
                "range": [0, 14],
                "gridcolor": PALETTE["mist"],
                "tickfont": {"size": 10, "color": PALETTE["teal"]},
            },
        )
        configure_gt_figure(fig_grid, margin_l=55, margin_r=25, margin_t=40, margin_b=30)

        # 8. Stiluri Overlay Sumar Faza 5 și Popover Confirmare
        summary_style: dict[str, str] = {
            "display": "flex" if modal_open else "none",
            "position": "fixed",
            "top": "0",
            "left": "0",
            "width": "100vw",
            "height": "100vh",
            "backgroundColor": "rgba(5, 91, 101, 0.45)",
            "backdropFilter": "blur(8px)",
            "zIndex": "9999",
            "alignItems": "center",
            "justifyContent": "center",
        }

        popover_style: dict[str, str] = {
            "display": "flex" if confirm_open else "none",
            "position": "fixed",
            "top": "0",
            "left": "0",
            "width": "100vw",
            "height": "100vh",
            "backgroundColor": "rgba(5, 91, 101, 0.3)",
            "backdropFilter": "blur(4px)",
            "zIndex": "10010",
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

        # 8. Stiluri Overlay Sumar Faza 5 și Popover Confirmare
        summary_style: dict[str, str] = {
            "display": "flex" if modal_open else "none",
            "position": "fixed",
            "top": "0",
            "left": "0",
            "width": "100vw",
            "height": "100vh",
            "backgroundColor": "rgba(5, 91, 101, 0.45)",
            "backdropFilter": "blur(8px)",
            "zIndex": "9999",
            "alignItems": "center",
            "justifyContent": "center",
        }

        popover_style: dict[str, str] = {
            "display": "flex" if confirm_open else "none",
            "position": "fixed",
            "top": "0",
            "left": "0",
            "width": "100vw",
            "height": "100vh",
            "backgroundColor": "rgba(5, 91, 101, 0.3)",
            "backdropFilter": "blur(4px)",
            "zIndex": "10010",
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
            pause_badge_style,
            waiting_msg,
            pill_pump_text,
            pill_pump_style,
            pill_utl_text,
            pill_utl_style,
            btn_open_sum_style,
            btn_top_replay_style,
            btn_pause_text,
            btn_pause_style,
            btn_stop_style,
            toast_msg,
            action_toast_style,
            kpi_dec_text,
            kpi_dec_sub,
            kpi_energy_pper,
            kpi_energy_extrap,
            kpi_energy_savings,
            kpi_cost_saved,
            kpi_cost_pct,
            kpi_comfort_rl,
            kpi_comfort_classic,
            agent_dec_action,
            agent_dec_reason,
            agent_dec_conf_val,
            agent_dec_conf_bar_style,
            agent_dec_history_elements,
            tl_pump_str,
            tl_pump_col,
            tl_pelt_str,
            tl_pelt_col,
            footer_status,
            fig_pper,
            fig_temp,
            fig_grid,
            summary_style,
            popover_style,
            sum_pper_val,
            sum_pper_scale,
            sum_energy_pct,
            sum_cost_pct,
            sum_co2_val,
        )

    return app
