"""Estudio 22: reglas de cuadrantes alineadas al reloj, catalogación sin mirar el día evaluado."""

import numpy as np
import pandas as pd

from tradingbot.research.study22 import QUAD, catalog_rule, holm, quad_rule


def test_mhi1_minority_uses_positions_3_to_5_of_previous_quadrant():
    idx = pd.date_range("2026-01-05 10:00", periods=10, freq="min", tz="UTC")
    col = np.array([1, 1, 1, 1, -1, 0, 0, 0, 0, 0], float)  # 10:02 verde, 10:03 verde, 10:04 roja
    d = quad_rule(col, idx.minute.to_numpy(), *QUAD["MHI1_minoria"])
    assert d[5] == -1 and np.isnan(d[:5]).all() and np.isnan(d[6:]).all()  # 10:05: contra la mayoría verde
    assert quad_rule(col, idx.minute.to_numpy(), *QUAD["MHI1_mayoria"])[5] == 1


def test_torres_gemeas_copies_position_1_into_position_5():
    idx = pd.date_range("2026-01-05 10:00", periods=5, freq="min", tz="UTC")
    col = np.array([-1, 1, 1, 1, 1], float)
    assert quad_rule(col, idx.minute.to_numpy(), *QUAD["Torres_Gemeas"])[4] == -1


def test_catalog_only_uses_previous_days():
    idx = pd.date_range("2026-01-01", periods=12 * 1440, freq="min", tz="UTC")
    col = np.where(idx.minute == 7, 1.0, -1.0)
    col[(idx.day == 12)] = 1.0  # el día evaluado no influye en su propia señal
    d = catalog_rule(col, idx, days=10, thr=0.8)
    day11 = idx.day == 11
    assert (d[day11 & (idx.minute == 7)] == 1).all() and (d[day11 & (idx.minute == 8)] == -1).all()
    assert (d[(idx.day == 12) & (idx.minute == 8)] == -1).all() and np.isnan(d[idx.day <= 10]).all()


def test_holm_is_monotone():
    assert holm([0.01, 0.04, 0.03]) == [0.03, 0.06, 0.06]
