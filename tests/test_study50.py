import math

import numpy as np
import pandas as pd

from tradingbot.research import study50 as s50


def _secs(n=3 * 3600, seed=0, start="2025-01-01"):
    rng = np.random.default_rng(seed)
    idx = pd.date_range(start, periods=n, freq="s", tz="UTC")
    c = 50_000 * np.exp(np.cumsum(rng.normal(0, 2e-4, n)))
    h = c * (1 + np.abs(rng.normal(0, 1e-4, n)))
    lo = c * (1 - np.abs(rng.normal(0, 1e-4, n)))
    v = rng.uniform(0.1, 2.0, n)
    tb = v * rng.uniform(0, 1, n)
    return pd.DataFrame({"h": h, "l": lo, "c": c, "v": v, "tb": tb}, index=idx)


def test_sliding_is_causal():
    sec = _secs()
    t = pd.date_range("2025-01-01 01:30", "2025-01-01 02:30", freq="10s", tz="UTC")
    vol = np.full(len(t), 1e-3)
    a = s50.sliding_block(sec, t, vol)
    cut = pd.Timestamp("2025-01-01 02:00", tz="UTC")
    alt = sec.copy()
    alt.loc[alt.index >= cut, ["h", "l", "c"]] *= 1.5  # todo lo que abre en `cut` o después cambia
    alt.loc[alt.index >= cut, ["v", "tb"]] *= 7
    b = s50.sliding_block(alt, t, vol)
    early = t <= cut  # una decisión en `cut` solo usa velas abiertas hasta cut − 1 s
    assert a[early].notna().all().all()
    pd.testing.assert_frame_equal(a[early], b[early])
    assert not np.allclose(a[~early].to_numpy(), b[~early].to_numpy(), equal_nan=True)


def test_sliding_values():
    n = 2 * 3600
    idx = pd.date_range("2025-01-01", periods=n, freq="s", tz="UTC")
    c = 100 + 0.01 * np.arange(n)
    sec = pd.DataFrame({"h": c, "l": c, "c": c, "v": 1.0, "tb": 1.0}, index=idx)
    t = pd.DatetimeIndex([idx[-1]])  # la última vela cerrada es la anterior
    f = s50.sliding_block(sec, t, np.array([0.001]))
    j = n - 2
    assert math.isclose(f["s_r5"].iloc[0], math.log(c[j] / c[j - 5]) / (0.001 * math.sqrt(5 / 60)))
    assert f["s_pos60"].iloc[0] == 1.0 and f["s_tib10"].iloc[0] == 1.0
    assert abs(f["s_vrel60"].iloc[0]) < 1e-9
    assert f["s_sec"].iloc[0] == t[0].second


def test_sliding_missing_seconds():
    sec = _secs(n=2 * 3600)
    t = pd.DatetimeIndex([sec.index[-1]])
    gap = sec.drop(sec.index[-40:-5])  # faltan 35 de las últimas 60 velas
    f = s50.sliding_block(gap, t, np.array([1e-3]))
    assert f.isna().all().all()


def test_take_signals_cooldown():
    t = pd.DatetimeIndex(pd.to_datetime([0, 10, 20, 70, 75, 200], unit="s", utc=True))
    p = np.array([0.60, 0.61, 0.30, 0.58, 0.62, 0.50])
    keep, side = s50.take_signals(t, p, np.ones(6, bool), 0.57)
    assert keep.tolist() == [0, 3]
    assert side[keep].tolist() == [1, 1]
    keep0, _ = s50.take_signals(t, p, np.ones(6, bool), 0.57, cooldown_s=0)
    assert keep0.tolist() == [0, 1, 2, 3, 4]


def test_coprime_step():
    for n in (10, 400_000, 3_100_000, 2_400_001):
        st = s50.coprime_step(n, 400_000)
        assert math.gcd(st, 6) == 1 and n / st <= 400_000


def test_summarize():
    t = pd.date_range("2025-09-01", periods=10, freq="h", tz="UTC")
    res = np.array([1, 1, 1, -1, 0, 1, -1, 1, 1, -1], float)
    s = s50.summarize(t, res, n_boot=50, n_days=2)
    assert s["operaciones"] == 10 and s["por_dia"] == 5
    assert math.isclose(s["acierto"], 6 / 9)
    assert math.isclose(s["ganancia_por_dia"], (6 * 0.86 - 3) / 2)
