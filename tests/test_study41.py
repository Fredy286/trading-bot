"""Estudio 41: ventanas de descarga, precio compuesto y resultado con la misma alineación que los Estudios 37 y 38."""

import numpy as np
import pandas as pd

from tradingbot.research.study41 import composite, outcome, pages


def test_pages_cover_the_month_without_overlap():
    start, end = pd.Timestamp("2026-02-01", tz="UTC"), pd.Timestamp("2026-03-01", tz="UTC")
    w = pages(start, end, 100)
    minutes = sum(int((b - a) / pd.Timedelta(minutes=1)) + 1 for a, b in w)
    assert minutes == 28 * 1440
    assert w[0][0] == start and w[-1][1] == end - pd.Timedelta(minutes=1)
    assert all(w[i + 1][0] == w[i][1] + pd.Timedelta(minutes=1) for i in range(len(w) - 1))


def test_composite_needs_all_venues_and_outcome_uses_next_close():
    t = pd.date_range("2026-01-01 00:00", periods=4, freq="min", tz="UTC")
    a = pd.Series([100.0, 101.0, 101.0, 99.0], index=t)
    b = pd.Series([100.0, 103.0, 101.0], index=t[:3])
    c = composite({"a": a, "b": b})
    assert list(c) == [100.0, 102.0, 101.0]  # el cuarto minuto falta en b
    r = outcome(c, t)
    assert r[0] == 1 and r[1] == -1 and np.isnan(r[2]) and np.isnan(r[3])
