"""Estudio 26: último precio antes de t + o s y etiqueta con el tic de cada moneda."""

import numpy as np
import pandas as pd

from tradingbot.research.study26 import label, last_before


def test_last_before_and_tick_label():
    t0 = pd.Timestamp("2026-01-01", tz="UTC")
    sec = pd.DataFrame({"c": np.arange(200, dtype=float)}, index=pd.date_range(t0, periods=200, freq="s"))
    r = last_before(sec, pd.DatetimeIndex([t0]), [60, 120])
    assert r.loc[t0, "R60"] == 59 and r.loc[t0, "R120"] == 119
    o, c = np.array([2.5000, 2.5000, 2.5000]), np.array([2.5001, 2.5000, 2.49995])
    assert label(o, c, 0.0001).tolist() == [1, 0, -1]
