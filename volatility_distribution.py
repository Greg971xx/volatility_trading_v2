import sqlite3
import pandas as pd
import plotly.graph_objects as go
from plotly.io import to_html

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QCheckBox
from PyQt6.QtWebEngineWidgets import QWebEngineView

class VolatilityDistributionViewer(QWidget):
    def __init__(self):
        super().__init__()

        self.ticker = "SPX"
        self.period = "1 an"
        self.mode = "C2C"
        self.use_abs = True
        self.db_path = "db/market_data.db"

        layout = QVBoxLayout()
        self.setLayout(layout)

        # Contrôles
        controls_layout = QHBoxLayout()

        self.mode_select = QComboBox()
        self.mode_select.addItems(["C2C", "O2C"])
        self.mode_select.currentTextChanged.connect(self.update_graph)
        controls_layout.addWidget(self.mode_select)

        self.abs_checkbox = QCheckBox("Volatilité absolue")
        self.abs_checkbox.setChecked(True)
        self.abs_checkbox.stateChanged.connect(self.update_graph)
        controls_layout.addWidget(self.abs_checkbox)

        layout.addLayout(controls_layout)

        self.web_view = QWebEngineView()
        layout.addWidget(self.web_view)

        self.update_graph()

    def set_parameters(self, ticker, period):
        self.ticker = ticker
        self.period = period
        self.update_graph()

    def update_graph(self):
        self.mode = self.mode_select.currentText()
        self.use_abs = self.abs_checkbox.isChecked()

        html = compute_volatility_distribution(
            ticker=self.ticker,
            db_path=self.db_path,
            mode=self.mode,
            use_abs=self.use_abs
        )
        self.web_view.setHtml(html)

def compute_volatility_distribution(ticker, db_path, mode="C2C", use_abs=True):
    table = f"{ticker.lower()}_data"
    conn = sqlite3.connect(db_path)
    df = pd.read_sql_query(f"SELECT date, open, close FROM {table} ORDER BY date ASC", conn)
    conn.close()

    df["date"] = pd.to_datetime(df["date"])
    df = df.drop_duplicates(subset="date")
    df = df[df["date"].dt.weekday < 5]

    if mode == "C2C":
        df["ret"] = df["close"].pct_change()
    else:
        df["ret"] = (df["close"] - df["open"]) / df["open"]

    df.dropna(subset=["ret"], inplace=True)
    df["year"] = df["date"].dt.year

    if use_abs:
        df["bin"] = pd.cut(
            abs(df["ret"]),
            bins=[0, 0.005, 0.01, 0.015, 0.02, 0.03, 0.05, 0.10, float('inf')],
            labels=["0% to 0.5%", "0.5% to 1%", "1% to 1.5%", "1.5% to 2%", "2% to 3%", "3% to 5%", "5% to 10%", "> 10%"],
            include_lowest=True
        )
        title = f"Répartition des variations journalières — {ticker} — |{mode}| (%)"
        color_map = None
    else:
        bins = [-float('inf'), -0.10, -0.05, -0.03, -0.02, -0.015, -0.01,
                -0.005, 0, 0.005, 0.01, 0.015, 0.02, 0.03, 0.05, 0.10, float('inf')]
        labels = ["< -10%", "-10% to -5%", "-5% to -3%", "-3% to -2%", "-2% to -1.5%",
                  "-1.5% to -1%", "-1% to -0.5%", "-0.5% to 0%",
                  "0% to 0.5%", "0.5% to 1%", "1% to 1.5%", "1.5% to 2%",
                  "2% to 3%", "3% to 5%", "5% to 10%", "> 10%"]
        df["bin"] = pd.cut(
            df["ret"], bins=bins, labels=labels,
            right=False, include_lowest=True
        )
        title = f"Répartition des variations journalières — {ticker} — {mode} signé (%)"
        color_map = {
            "< -10%": "#6e0000", "-10% to -5%": "#990000", "-5% to -3%": "#cc0000", "-3% to -2%": "#e63900",
            "-2% to -1.5%": "#ff6600", "-1.5% to -1%": "#ff8533", "-1% to -0.5%": "#ff9966", "-0.5% to 0%": "#ffcc99",
            "0% to 0.5%": "#99ccff", "0.5% to 1%": "#66b2ff", "1% to 1.5%": "#3399ff", "1.5% to 2%": "#0073e6",
            "2% to 3%": "#0059b3", "3% to 5%": "#004080", "5% to 10%": "#00264d", "> 10%": "#001a33"
        }

    df = df[df["bin"].notna()]
    counts = df.groupby(["year", "bin"], observed=True).size().unstack(fill_value=0)
    counts = counts.sort_index(axis=1)

    fig = go.Figure()
    for col in counts.columns:
        fig.add_trace(go.Bar(
            name=str(col),
            x=counts.index,
            y=counts[col],
            marker_color=color_map[str(col)] if color_map else None
        ))

    fig.update_layout(
        barmode='stack',
        title=title,
        xaxis_title="Année",
        yaxis_title="Nombre de séances",
        template="plotly_dark",
        legend_title=""
    )

    return to_html(fig, include_plotlyjs='cdn')
