"""Estudio 19: solo velas cuyo vencimiento cae en un cuarto de hora exacto."""

import pandas as pd

from tradingbot.research.study19 import quarter_aligned


def test_quarter_alignment_for_each_remaining_time():
    idx = pd.date_range("2024-01-01 10:00", periods=60, freq="min", tz="UTC")
    # R = 1: aviso en la vela 10:13 (segundo 50), entrada 10:14, vence 10:15.
    assert [t.strftime("%H:%M") for t in idx[quarter_aligned(idx, 1)]] == ["10:13", "10:28", "10:43", "10:58"]
    # R = 2: aviso en 10:12, entrada 10:13, vence 10:15.
    assert idx[quarter_aligned(idx, 2)][0].strftime("%H:%M") == "10:12"
    assert quarter_aligned(idx, 5).sum() == 4
