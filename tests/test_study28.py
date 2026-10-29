"""Estudio 28: ventana anclada al cierre de Nueva York (cambia de hora UTC con el horario de verano)."""

import pandas as pd

from tradingbot.research.study28 import one_at_a_time, windows


def test_new_york_window_moves_with_daylight_saving():
    t = pd.DatetimeIndex(["2026-07-01 21:30", "2026-01-15 21:30", "2026-01-16 00:30"], tz="UTC")
    w = windows(t)
    assert w["H28a"].tolist() == [True, True, False]
    assert w["H28b"].tolist() == [True, False, True]  # en enero, 21:30 UTC son las 16:30 NY (antes del cierre)


def test_one_trade_at_a_time():
    t = pd.DatetimeIndex(["2026-01-01 22:00", "2026-01-01 22:01", "2026-01-01 22:03"], tz="UTC")
    assert one_at_a_time(t).tolist() == [True, False, True]
