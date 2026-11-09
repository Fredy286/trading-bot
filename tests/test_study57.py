"""Estudio 57: medidas en el cambio de minuto, diferencia en diferencias, Holm y ejecución con datos sintéticos."""

import json

import numpy as np
import pandas as pd

from tradingbot.research import study57


def _sec(start, n, price=None, vol=None):
    idx = pd.date_range(start, periods=n, freq="s", tz="UTC")
    c = np.full(n, 100.0) if price is None else price
    v = np.ones(n) if vol is None else vol
    return pd.DataFrame({"c": c, "v": v}, index=idx)


def test_boundary_share_and_reversal():
    start = pd.Timestamp("2026-03-01 00:00", tz="UTC")
    n = 4 * 60
    price = np.full(n, 100.0)
    vol = np.ones(n)
    t = 120  # cambio de minuto en 00:02:00 (índice 120)
    price[t - 10:t] = 101.0  # sube en los últimos 10 s …
    price[t:t + 10] = 100.5  # … y baja en los 10 s siguientes
    vol[t - 10:t] = 5.0
    sec = _sec(start, n, price, vol)
    minutes = pd.DatetimeIndex([start + pd.Timedelta(minutes=2)])
    tab = study57.boundary_table(sec, minutes)
    # cuota = 10·5 / (50·1 + 10·5)
    assert np.isclose(tab["cuota"].iloc[0], 50 / 100)
    assert tab["reversion"].iloc[0] == 1.0


def test_boundary_uses_no_future_beyond_10s():
    start = pd.Timestamp("2026-03-01 00:00", tz="UTC")
    n = 4 * 60
    sec = _sec(start, n, np.linspace(100, 101, n))
    minutes = pd.DatetimeIndex([start + pd.Timedelta(minutes=2)])
    a = study57.boundary_table(sec, minutes)
    sec2 = sec.copy()
    sec2.iloc[120 + 10:, 0] = 50.0  # cambiar precios desde t + 10 s no cambia nada
    b = study57.boundary_table(sec2, minutes)
    pd.testing.assert_frame_equal(a, b)


def test_is_m5():
    t = pd.DatetimeIndex(["2026-01-01 00:05", "2026-01-01 00:06", "2026-01-01 00:15"], tz="UTC")
    assert list(study57.is_m5(t)) == [True, False, True]


def test_did_detects_planted_effect():
    t = pd.date_range("2025-09-01", "2026-09-30 23:59", freq="7min", tz="UTC")
    g = study57.is_m5(t)
    rng = np.random.default_rng(1)
    v = rng.normal(0, 1, len(t))
    v[g & (t >= pd.Timestamp("2026-02-12", tz="UTC"))] += 0.5
    r = study57.did(v, t, g, study57.LAUNCH, 1, n_boot=200)
    assert 0.35 < r["D"] < 0.65 and r["p_unilateral"] < 0.01
    r0 = study57.did(rng.normal(0, 1, len(t)), t, g, study57.LAUNCH, 1, n_boot=200)
    assert r0["p_unilateral"] > 0.01


def test_holm():
    out = study57.holm({"a": 0.01, "b": 0.02, "c": 0.04})
    assert out["a"]["pasa"] and out["b"]["pasa"] and out["c"]["pasa"]
    out = study57.holm({"a": 0.01, "b": 0.03, "c": 0.04})
    assert out["a"]["pasa"] and not out["b"]["pasa"] and not out["c"]["pasa"]


def test_run_synthetic(tmp_path):
    work = tmp_path / "w"
    (work / "seg").mkdir(parents=True)
    rng = np.random.default_rng(2)
    for ym in ("2026-01", "2026-02", "2026-03"):
        start = pd.Timestamp(ym + "-01", tz="UTC")
        n = 3 * 24 * 3600  # 3 días por mes
        price = 100 * np.exp(np.cumsum(rng.normal(0, 1e-4, n)))
        _sec(start, n, price, rng.uniform(0.5, 2, n)).to_parquet(work / "seg" / f"{ym}.parquet")
    te = pd.date_range("2026-01-01", "2026-03-03", freq="55min", tz="UTC")
    trades = pd.DataFrame({"res": rng.choice([-1.0, 1.0, 0.0], len(te), p=[0.45, 0.5, 0.05])}, index=te)
    import pytest
    mp = pytest.MonkeyPatch()
    mp.setattr(study57, "START", "2026-01-01")
    mp.setattr(study57, "END", "2026-04-01")
    mp.setattr(study57, "PLACEBO", "2026-01-02")
    mp.setattr(study57, "LAUNCH", "2026-02-12")
    try:
        rep = study57.run(work=work, out_dir=tmp_path / "r", n_boot=50, download=False, trades=trades, log=lambda *_: None)
    finally:
        mp.undo()
    assert set(rep["hipotesis"]) == {"H57a", "H57b", "H57c"}
    assert rep["hipotesis"]["H57c"]["potencia_minima"] is False and rep["hipotesis"]["H57c"]["pasa"] is False
    assert json.loads((tmp_path / "r" / "resultado.json").read_text())["hipotesis"]["H57a"]["D"] is not None
