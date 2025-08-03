import sqlite3
import pandas as pd
import plotly.graph_objects as go
from plotly.io import to_html

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QCheckBox
from PyQt6.QtWebEngineWidgets import QWebEngineView

class VolatiliteJourSemaineViewer(QWidget):
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

        html = compute_volatilite_jour_semaine(
            ticker=self.ticker,
            db_path=self.db_path,
            mode=self.mode,
            use_abs=self.use_abs
        )
        self.web_view.setHtml(html)

def compute_volatilite_jour_semaine(ticker, db_path, mode="C2C", use_abs=True):
    table = f"{ticker.lower()}_data"
    conn = sqlite3.connect(db_path)
    df = pd.read_sql_query(f"SELECT date, open, close FROM {table} ORDER BY date ASC", conn)
    conn.close()

    df["date"] = pd.to_datetime(df["date"])
    df = df.drop_duplicates(subset="date")
    df = df[df["date"].dt.weekday < 5]  # uniquement lundi à vendredi

    if mode == "C2C":
        df["ret"] = df["close"].pct_change()
    else:
        df["ret"] = (df["close"] - df["open"]) / df["open"]

    df.dropna(subset=["ret"], inplace=True)
    df["year"] = df["date"].dt.year
    df["weekday"] = df["date"].dt.day_name()

    if use_abs:
        df["vol"] = df["ret"].abs() * 100
        title = f"\U0001F525 Volatilité absolue moyenne par jour de la semaine ({mode}) — {ticker}"
        colorbar_title = "Volatilité absolue (%)"
    else:
        df["vol"] = df["ret"] * 100
        title = f"\U0001F525 Volatilité signée moyenne par jour de la semaine ({mode}) — {ticker}"
        colorbar_title = "Volatilité (%)"

    pivot = df.pivot_table(index="year", columns="weekday", values="vol", aggfunc="mean")
    pivot = pivot[["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]]

    # Crée la heatmap avec valeurs visibles dans chaque case
    fig = go.Figure(data=go.Heatmap(
        z=pivot.values,
        x=pivot.columns,
        y=pivot.index,
        colorscale="RdBu_r" if not use_abs else "Blues",
        colorbar=dict(title=colorbar_title),
        text=pivot.round(2).astype(str),
        texttemplate="%{text}%",  # ✅ Valeur visible dans chaque case
        hovertemplate="weekday: %{x}<br>year: %{y}<br>Volatilité : %{z:.2f}%<extra></extra>"
    ))

    fig.update_layout(
        title=title,
        xaxis_title="Jour de la semaine",
        yaxis_title="Année",
        template="plotly_dark"
    )

    return to_html(fig, include_plotlyjs='cdn')