"""Estudio 34: referencia del diferencial con solo días anteriores."""

import numpy as np
import pandas as pd

from tradingbot.research.study34 import SPREAD_DAYS, spread_reference


def test_spread_reference_uses_only_previous_days():
    idx = pd.date_range("2025-01-01 21:00", periods=(SPREAD_DAYS + 3) * 1440, freq="min", tz="UTC")
    sp = pd.Series(1.0, index=idx)
    sp[idx.floor("D") == idx.floor("D")[-1]] = 99.0  # el último día no puede influir en su propia referencia
    ref = spread_reference(pd.DataFrame({"spread_med": sp}, index=idx))
    assert np.isnan(ref.iloc[:SPREAD_DAYS]).all()
    assert ref.iloc[-1] == 1.0
