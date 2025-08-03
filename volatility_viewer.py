from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QComboBox, QCheckBox, QPushButton,
    QHBoxLayout, QGroupBox, QFormLayout, QSizePolicy
)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtCore import QUrl
import sqlite3
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
import tempfile


class VolatilityViewer(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Volatilité Réalisée")

        self.ticker = "SPX"
        self.period = "1 an"
        self.vol_type = "Les deux"
        self.mode = "Pourcentage"
        self.show_daily = True

        main_layout = QVBoxLayout()
        options_layout = QHBoxLayout()

        self.web_view = QWebEngineView()
        self.web_view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.vol_type_select = QComboBox()
        self.vol_type_select.addItems(["C2C", "O2C", "Les deux"])
        self.vol_type_select.currentIndexChanged.connect(self.update_plot)

        self.display_mode = QComboBox()
        self.display_mode.addItems(["Pourcentage", "Valeur absolue"])
        self.display_mode.currentIndexChanged.connect(self.update_plot)

        self.show_daily_checkbox = QCheckBox("Afficher la volatilité journalière")
        self.show_daily_checkbox.setChecked(True)
        self.show_daily_checkbox.stateChanged.connect(self.update_plot)

        update_button = QPushButton("Mettre à jour le graphique")
        update_button.clicked.connect(self.update_plot)

        self.form_layout = QFormLayout()
        self.form_layout.setSpacing(5)
        self.form_layout.addRow("Type de VR :", self.vol_type_select)
        self.form_layout.addRow("Affichage :", self.display_mode)
        self.form_layout.addRow("", self.show_daily_checkbox)
        self.form_layout.addRow("", update_button)

        self.group_box = QGroupBox("Options de volatilité")
        self.group_box.setCheckable(True)
        self.group_box.setChecked(True)
        self.group_box.setLayout(self.form_layout)
        self.group_box.toggled.connect(self.toggle_option_visibility)

        options_layout.addWidget(self.group_box)

        main_layout.addLayout(options_layout)
        main_layout.addWidget(self.web_view, stretch=1)
        self.setLayout(main_layout)

    def toggle_option_visibility(self, checked):
        for i in range(self.form_layout.count()):
            item = self.form_layout.itemAt(i)
            if item and item.widget():
                item.widget().setVisible(checked)

    def set_parameters(self, ticker: str, period: str):
        self.ticker = ticker
        self.period = period
        self.update_plot()

    def update_plot(self):
        self.vol_type = self.vol_type_select.currentText()
        self.mode = self.display_mode.currentText()
        self.show_daily = self.show_daily_checkbox.isChecked()
        self.plot()

    def plot(self):
        ticker = self.ticker
        period = self.period
        vol_type = self.vol_type
        mode = self.mode

        conn = sqlite3.connect("db/market_data.db")
        df = pd.read_sql(f"SELECT * FROM {ticker.lower()}_data", conn, parse_dates=["date"])
        conn.close()

        df = df.sort_values("date")

        if period == "1 an":
            df = df[df["date"] >= datetime.now() - timedelta(days=365)]
        elif period == "5 ans":
            df = df[df["date"] >= datetime.now() - timedelta(days=5 * 365)]

        df.dropna(inplace=True)
        df["C2C"] = df["close"].pct_change()
        df["O2C"] = (df["close"] - df["open"]) / df["open"]

        if mode == "Valeur absolue":
            df["C2C"] = df["C2C"].abs()
            df["O2C"] = df["O2C"].abs()

        for window in [5, 20, 60, 120, 252]:
            df[f"C2C_MA_{window}"] = df["C2C"].rolling(window).mean()
            df[f"O2C_MA_{window}"] = df["O2C"].rolling(window).mean()

        fig = go.Figure()
        format_y = lambda y: y * 100
        suffix_y = "%"

        if self.show_daily:
            if vol_type in ["C2C", "Les deux"]:
                fig.add_trace(go.Scatter(x=df['date'], y=format_y(df["C2C"]), mode='lines', name="C2C journalier", line=dict(color='blue', width=1, dash='dot')))
            if vol_type in ["O2C", "Les deux"]:
                fig.add_trace(go.Scatter(x=df['date'], y=format_y(df["O2C"]), mode='lines', name="O2C journalier", line=dict(color='orange', width=1, dash='dot')))

        if vol_type in ["C2C", "Les deux"]:
            for window in [5, 20, 60, 120, 252]:
                fig.add_trace(go.Scatter(x=df['date'], y=format_y(df[f"C2C_MA_{window}"]), mode='lines', name=f"C2C MM{window}"))

        if vol_type in ["O2C", "Les deux"]:
            for window in [5, 20, 60, 120, 252]:
                fig.add_trace(go.Scatter(x=df['date'], y=format_y(df[f"O2C_MA_{window}"]), mode='lines', name=f"O2C MM{window}"))

        fig.add_trace(go.Scatter(x=df["date"], y=df["close"], mode="lines", name="Prix", yaxis="y2", line=dict(color="gray", dash="dot")))

        fig.update_layout(
            title=f"{ticker} - Volatilité Réalisée ({vol_type})",
            xaxis=dict(title="Date"),
            yaxis=dict(title=f"Volatilité réalisée {suffix_y}"),
            yaxis2=dict(title="Prix du sous-jacent", overlaying="y", side="right"),
            margin=dict(l=20, r=40, t=50, b=20),
            height=800,
            template="plotly_dark"
        )

        with tempfile.NamedTemporaryFile(delete=False, suffix=".html") as f:
            fig.write_html(f.name)
            self.web_view.load(QUrl.fromLocalFile(f.name))
