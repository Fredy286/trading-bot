"""Estudio 27: precio del último tick antes de un instante, con antigüedad máxima."""

import numpy as np
import pandas as pd

from tradingbot.research.study27 import price_at


def test_price_at_uses_last_tick_before_and_rejects_stale():
    idx = pd.DatetimeIndex(["2026-04-01 21:00:00", "2026-04-01 21:00:07", "2026-04-01 21:03:00"], tz="UTC")
    sec = pd.Series([1.0, 2.0, 3.0], index=idx)
    when = pd.DatetimeIndex(["2026-04-01 21:00:05", "2026-04-01 21:00:08", "2026-04-01 21:02:30"], tz="UTC")
    out = price_at(sec, when)
    assert out[0] == 1.0 and out[1] == 2.0 and np.isnan(out[2])  # 21:02:29 − 21:00:07 > 60 s
