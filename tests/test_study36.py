"""Estudio 36: con velas, entrada en la apertura de t y salida en el cierre de t + 2."""

import numpy as np
import pandas as pd

from tradingbot.research.study36 import trades


def test_trades_use_open_of_entry_and_close_of_last_candle():
    idx = pd.date_range("2026-04-01 20:30", periods=60, freq="min", tz="UTC")
    c = 1.0 + np.random.default_rng(3).normal(0, 1e-5, 60)
    c[30] = 0.99  # la vela de las 21:00 cierra muy abajo → CALL a las 21:01
    bars = pd.DataFrame({"o": c, "h": c, "l": c, "c": c}, index=idx)
    bars.loc[idx[31], "o"], bars.loc[idx[33], "c"] = 1.0, 1.01
    t = trades(bars, 20, 2.0, 3, "EURGBP")
    first = t.loc[pd.Timestamp("2026-04-01 21:01", tz="UTC")]
    assert first["dir"] == 1 and first["res"] == 1
