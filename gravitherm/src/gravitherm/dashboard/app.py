"""Dashboard Plotly/Dash - compara agentul RL vs. baseline ON/OFF.

Rulare: python -m gravitherm.dashboard.app
Fisier comun - coordonati-va inainte de a-l modifica (vezi CONTRIBUTING.md).
"""

from dash import Dash, dcc, html

app = Dash(__name__)

app.layout = html.Div(
    [
        html.H1("GraviTherm - RL vs Baseline"),
        dcc.Graph(id="temperature-graph"),
        dcc.Graph(id="power-graph"),
        # TODO(echipa): populati graficele cu date din simulation/env.py (Faza I)
        # si ulterior din iot/influx_writer.py (Faza III).
    ]
)

if __name__ == "__main__":
    app.run(debug=True)
