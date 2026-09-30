"""Fuentes de velas para el bucle en vivo.

- ReplayFeed: reproduce velas históricas o sintéticas con un reloj simulado (demostraciones y pruebas).
- BinancePollingFeed: API pública de Binance (sin credenciales). El análisis del formato está probado
  con datos de ejemplo; la conexión real NO se probó desde el entorno de desarrollo (red bloqueada).
Cada lectura devuelve la hora de recepción para registrar cuándo estuvo disponible el dato.
"""

from __future__ import annotations

from datetime import datetime

import pandas as pd
import requests

from ..data.binance import KLINE_COLS
from ..data.clean import to_canonical
from ..timeutil import utcnow


class ReplayFeed:
    def __init__(self, bars: pd.DataFrame, feed_latency_s: float = 2.0):
        self.bars = bars
        self.latency = pd.Timedelta(seconds=feed_latency_s)

    def get(self, now_utc: datetime, lookback: int = 2000) -> tuple[pd.DataFrame, datetime]:
        """Velas cuyo cierre (t + 60 s) más la latencia del proveedor ocurrió antes de `now_utc`."""
        cutoff = pd.Timestamp(now_utc) - self.latency - pd.Timedelta(minutes=1)
        vis = self.bars[self.bars.index <= cutoff]
        return vis.iloc[-lookback:], now_utc


class BinancePollingFeed:
    URL = "https://api.binance.com/api/v3/klines"

    def __init__(self, symbol: str, session=None):
        self.symbol = symbol.upper()
        self.session = session or requests.Session()

    @staticmethod
    def parse(payload: list, now_utc: datetime) -> pd.DataFrame:
        df = pd.DataFrame(payload, columns=KLINE_COLS)
        idx = pd.to_datetime(df["open_time"].astype("int64"), unit="ms", utc=True)
        close_time = pd.to_datetime(df["close_time"].astype("int64"), unit="ms", utc=True)
        raw = pd.DataFrame(index=pd.DatetimeIndex(idx, name="time"))
        for side in ("bid", "ask"):
            for k, col in (("o", "open"), ("h", "high"), ("l", "low"), ("c", "close")):
                raw[f"{side}_{k}"] = df[col].astype(float).to_numpy()
        raw["bid_v"] = df["volume"].astype(float).to_numpy()
        raw["ask_v"] = 0.0
        raw["trades"] = df["trades"].astype(float).to_numpy()
        raw = raw[(close_time < pd.Timestamp(now_utc)).to_numpy()]  # solo velas ya cerradas
        bars, _ = to_canonical(raw)
        return bars

    def get(self, now_utc: datetime | None = None, lookback: int = 1000) -> tuple[pd.DataFrame, datetime]:
        r = self.session.get(self.URL, params={"symbol": self.symbol, "interval": "1m", "limit": lookback},
                             timeout=10)
        r.raise_for_status()
        received = utcnow()
        return self.parse(r.json(), now_utc or received), received
