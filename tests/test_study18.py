"""Estudio 18: precios de entrada y salida con velas de 1 s y regla de «una operación a la vez»."""

import numpy as np
import pandas as pd

from tradingbot.research.study18 import label, one_at_a_time, price_table


def test_price_table_takes_last_trade_before_each_offset():
    idx = pd.date_range("2024-01-01", periods=1200, freq="s", tz="UTC")
    sec = pd.DataFrame({"c": 100 + 0.01 * np.arange(1200)}, index=idx)
    minutes = pd.date_range("2024-01-01", periods=2, freq="min", tz="UTC")
    t = price_table(sec, minutes, [60, 240])
    # Último precio antes de t + 60 s = cierre del segundo 59; antes de t + 240 s = segundo 239.
    assert np.isclose(t["Q60"].iloc[0], 100 + 0.59) and np.isclose(t["Q240"].iloc[1], 100 + 0.01 * 299)
    gap = sec.drop(idx[50:60])  # 10 s sin operaciones antes de t + 60 s
    assert np.isnan(price_table(gap, minutes, [60])["Q60"].iloc[0])


def test_label_and_one_trade_at_a_time():
    minutes = pd.date_range("2024-01-01", periods=10, freq="min", tz="UTC")
    prices = pd.DataFrame({"Q60": 100.0, "Q240": [101.0, 99.0] * 5}, index=minutes)
    assert label(prices, 10, 180).tolist() == [1, -1] * 5
    take = np.ones(10, bool)
    keep = one_at_a_time(minutes, take, 180)
    assert keep.tolist() == [True, False, False, True, False, False, True, False, False, True]
