"""Estudio 42: variables del compuesto sin mirar el futuro y etiqueta del blitz de 3 min."""

import numpy as np
import pandas as pd

from tradingbot.research.study42 import comp_features, label3


def _series(n=80, seed=1):
    t = pd.date_range("2026-01-01", periods=n, freq="min", tz="UTC")
    rng = np.random.default_rng(seed)
    comp = pd.Series(100_000 + np.cumsum(rng.normal(0, 10, n)), index=t)
    binance = comp + rng.normal(8, 2, n)
    return t, comp, binance


def test_comp_features_only_use_closes_up_to_t_minus_1():
    t, comp, binance = _series()
    vol = pd.Series(1e-4, index=t)
    f = comp_features(comp, binance, vol, t)
    i = 70
    assert np.isclose(f["c_r1"].iloc[i], np.log(comp.iloc[i - 1] / comp.iloc[i - 2]) / 1e-4)
    assert np.isclose(f["c_r3"].iloc[i], np.log(comp.iloc[i - 1] / comp.iloc[i - 4]) / (1e-4 * np.sqrt(3)))
    later = comp.copy()
    later.iloc[i:] += 500.0  # cambiar el cierre de t y los siguientes no debe tocar las variables de t
    g = comp_features(later, binance, vol, t)
    pd.testing.assert_series_equal(f.iloc[i], g.iloc[i])


def test_label3_compares_close_of_t_plus_3_with_close_of_t():
    t = pd.date_range("2026-01-01", periods=6, freq="min", tz="UTC")
    c = pd.Series([10.0, 11.0, 9.0, 10.0, 12.0, 10.0], index=t)
    y = label3(c, t)
    assert list(y[:3]) == [0.0, 1.0, 1.0]  # 10→10 empate, 11→12 sube, 9→10 sube
    assert np.isnan(y[3:]).all()
