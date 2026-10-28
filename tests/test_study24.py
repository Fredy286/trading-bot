"""Estudio 24: puntos de precio dentro del minuto (último precio antes de t + o s)."""

import numpy as np
import pandas as pd

from tradingbot.research.study24 import price_points


def test_price_points_use_only_seconds_before_the_offset():
    t0 = pd.Timestamp("2026-01-01 00:00", tz="UTC")
    idx = pd.date_range(t0, periods=120, freq="s")
    sec = pd.DataFrame({"c": np.arange(120, dtype=float)}, index=idx)
    pts = price_points(sec, pd.DatetimeIndex([t0]))
    assert pts.loc[t0, "X50"] == 49 and pts.loc[t0, "X30"] == 29  # vela de 1 s que abre en t + 49 s
    gap = sec.drop(idx[40:50])
    assert np.isnan(price_points(gap, pd.DatetimeIndex([t0])).loc[t0, "X50"])  # hueco > 5 s
