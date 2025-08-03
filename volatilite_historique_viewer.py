import sqlite3
import pandas as pd
import plotly.graph_objects as go
from plotly.io import to_html

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPushButton
from PyQt6.QtWebEngineWidgets import QWebEngineView
from datetime import datetime, timedelta

from core.greeks_fetcher import update_iv_from_greeks  # ✅ nouveau


class VolatiliteHistoriqueViewer(QWidget):
    def __init__(self):
        super().__init__()

        self.ticker = "SPX"
        self.period = "1 an"
        self.db_path = "db/market_data.db"

        layout = QVBoxLayout()
        self.setLayout(layout)

        self.update_button = QPushButton("🔁 Mettre à jour IV + Greeks")
        self.update_button.clicked.connect(self.update_iv_data)
        layout.addWidget(self.update_button)

        self.web_view = QWebEngineView()
        layout.addWidget(self.web_view)

        self.update_graph()

    def set_parameters(self, ticker, period):
        self.ticker = ticker
        self.period = period
        self.update_graph()

    def update_graph(self):
        html = compute_volatilite_historique(
            ticker=self.ticker,
            db_path=self.db_path,
            period=self.period
        )
        self.web_view.setHtml(html)

    def update_iv_data(self):
        try:
            print(f"⏳ Mise à jour IV + Greeks pour {self.ticker}...")
            iv_0dte, _ = update_iv_from_greeks(self.ticker)

            if iv_0dte:
                print(f"✅ IV 0DTE calculée pour {self.ticker} : {iv_0dte * 100:.2f}%")
            else:
                print(f"⚠️ IV 0DTE non disponible pour {self.ticker}")

            self.update_graph()

        except Exception as e:
            print(f"❌ Erreur lors de la mise à jour IV/Greeks pour {self.ticker} : {e}")


def compute_volatilite_historique(ticker, db_path, period="1 an"):
    table = f"{ticker.lower()}_data"
    conn = sqlite3.connect(db_path)

    df = pd.read_sql_query(f"SELECT date, close FROM {table} ORDER BY date ASC", conn)
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    df = df.drop_duplicates(subset="date")
    df = df[df["date"].dt.weekday < 5]
    df = df.sort_values("date")
    df["returns"] = df["close"].pct_change()

    # Lecture IV depuis greeks_observations (delta ~ 0.5)
    iv_df = pd.read_sql_query(f"""
        SELECT date, iv, delta
        FROM greeks_observations
        WHERE ticker = ? AND type = 'CALL'
    """, conn, params=(ticker,))
    conn.close()
    iv_df["date"] = pd.to_datetime(iv_df["date"]).dt.normalize()

    # Choisir IV avec delta proche de 0.5
    iv_df = iv_df.copy()
    iv_df["delta_distance"] = (iv_df["delta"] - 0.5).abs()
    iv_filtered = iv_df.sort_values("delta_distance").drop_duplicates(subset="date")
    iv_filtered = iv_filtered.rename(columns={"iv": "iv_0dte"})[["date", "iv_0dte"]]
    iv_filtered["iv_0dte"] *= 100  # ✅ pour affichage en pourcentage

    # Ajouter ligne aujourd'hui si manquante
    today = pd.to_datetime(datetime.now().date()).normalize()
    if today not in df["date"].values:
        last_close = df["close"].iloc[-1]
        new_row = pd.DataFrame([{
            "date": today,
            "close": last_close,
            "returns": None,
            "HV5": None,
            "HV20": None,
            "HV60": None,
            "HV120": None,
            "HV252": None,
            "iv_0dte": None
        }])
        df = pd.concat([df, new_row[df.columns]], ignore_index=True)
        df = df.sort_values("date")

    df = pd.merge(df, iv_filtered, on="date", how="left")

    if period == "1 an":
        df = df[df["date"] >= datetime.now() - timedelta(days=365)]
    elif period == "5 ans":
        df = df[df["date"] >= datetime.now() - timedelta(days=5 * 365)]

    for window in [5, 20, 60, 120, 252]:
        df[f"HV{window}"] = df["returns"].rolling(window).std() * (252 ** 0.5) * 100

    fig = go.Figure()

    for window in [5, 20, 60, 120, 252]:
        fig.add_trace(go.Scatter(
            x=df["date"],
            y=df[f"HV{window}"],
            mode="lines",
            name=f"HV{window}"
        ))

    if df["iv_0dte"].notna().any():
        fig.add_trace(go.Scatter(
            x=df["date"],
            y=df["iv_0dte"],
            mode="lines+markers",
            name="IV 0DTE",
            line=dict(color="orange", dash="dash"),
            marker=dict(size=6)
        ))

    fig.update_layout(
        title=f"Volatilité Historique — {ticker}",
        xaxis_title="Date",
        yaxis_title="Volatilité annualisée (%)",
        template="plotly_dark"
    )

    return to_html(fig, include_plotlyjs='cdn')