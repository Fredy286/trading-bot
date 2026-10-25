"""Estudio 7: las herramientas siguen sus definiciones fijas y no miran el futuro."""

import numpy as np
import pandas as pd

from tradingbot.research.contracts import BinaryContract
from tradingbot.research.study7 import _policy, analog_scores, kalman_slope, patterns


def test_kalman_tracks_a_linear_trend_and_skips_missing_values():
    y = 0.001 * np.arange(500.0)
    s = kalman_slope(y)
    assert abs(s[-1] - 0.001) < 1e-6
    y2 = y.copy()
    y2[200:205] = np.nan  # sin observación: solo predice
    s2 = kalman_slope(y2)
    assert not np.isnan(s2[200:205]).any() and abs(s2[-1] - 0.001) < 1e-6
    # Causal: cambiar el futuro no cambia el pasado.
    y3 = y.copy()
    y3[301:] += 1.0
    assert np.array_equal(kalman_slope(y3)[:301], s[:301])


def test_patterns_use_only_the_last_12_returns():
    idx = pd.date_range("2024-01-01", periods=100, freq="min", tz="UTC")
    logc = pd.Series(np.cumsum(np.random.default_rng(0).normal(0, 1e-3, 100)), index=idx)
    vol = pd.Series(2.0, index=idx)
    p = patterns(logc, vol)
    t = 50
    expect = [(logc.iloc[t - k] - logc.iloc[t - k - 1]) / 2.0 for k in range(12)]
    assert np.allclose(p[t], expect) and np.isnan(p[10]).any()


def test_analog_scores_match_brute_force_neighbours():
    rng = np.random.default_rng(1)
    lib_x, lib_y = rng.normal(size=(3000, 12)), rng.choice([-1.0, 0.0, 1.0], size=3000)
    q = rng.normal(size=(7, 12))
    got = analog_scores(lib_x, lib_y, q, k=25, chunk=3)
    for i in range(7):
        d = ((lib_x - q[i]) ** 2).sum(axis=1)
        assert np.isclose(got[i], lib_y[np.argsort(d)[:25]].mean(), atol=1e-6)


def test_policy_counts_wins_losses_and_refunded_ties():
    c = BinaryContract(0.85, "refund")
    p_up = np.array([0.7, 0.3, 0.7, 0.5, 0.7])
    dirs = np.array([1, -1, 0, 1, -1])
    r = _policy(p_up, dirs, np.zeros(5), c, 0.02)  # p = 0,5 no pasa el margen
    assert r["operaciones"] == 4 and r["aciertos"] == 2 and r["sin_empate"] == 3
    assert np.isclose(r["ev"], (0.85 + 0.85 + 0.0 - 1.0) / 4)
