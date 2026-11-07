"""Estudio 49: sello del registro, carga de señales y filtro con datos sintéticos (nunca con el registro real)."""

import json

import numpy as np
import pandas as pd
import pytest

from tradingbot.research import study49


def _write(tmp_path, n=4000, seed=0):
    rng = np.random.default_rng(seed)
    t = pd.date_range("2026-10-26", periods=n, freq="25min", tz="UTC")
    # régimen bueno / malo por semanas, para que la racha tenga información
    good = (t.isocalendar().week.to_numpy() % 2) == 0
    win = rng.random(n) < np.where(good, 0.60, 0.50)
    res = np.where(rng.random(n) < 0.05, "empate", np.where(win, "gana", "pierde"))
    d = tmp_path / "btc"
    d.mkdir()
    with open(d / "x.jsonl", "w", encoding="utf-8") as f:
        for ti, r in zip(t, res):
            f.write(json.dumps({"vela": ti.isoformat(), "resultado": str(r), "p": 0.58, "umbral_060": False,
                                "modelo": "m"}) + "\n")
        f.write(json.dumps({"vela": t[0].isoformat(), "resultado": None, "p": 0.5}) + "\n")
    return d


def test_sellado_no_evalua(tmp_path):
    with pytest.raises(SystemExit):
        study49.run(tmp_path, tmp_path / "o", hoy=pd.Timestamp("2027-01-18", tz="UTC"))


def test_carga_filtra_ventana_y_sin_resultado(tmp_path):
    d = _write(tmp_path, n=100)
    df = study49.load_signals(d)
    assert len(df) == 100 and df["vela"].is_monotonic_increasing
    assert set(df["res"].unique()) <= {-1.0, 0.0, 1.0}
    assert df["vela"].min() >= study49.START


def test_resueltas_tres_minutos_antes():
    t = pd.date_range("2026-10-26", periods=3, freq="min", tz="UTC")
    from tradingbot.research.study48 import streak_rates
    import tradingbot.research.study48 as s48
    old = s48.MIN_DAYS_N
    s48.MIN_DAYS_N = 1
    try:
        _, b = streak_rates(t, t + study49.RESOLVED_AFTER, np.array([1.0, 1.0, 1.0]))
    finally:
        s48.MIN_DAYS_N = old
    assert np.isnan(b).all()  # a 1–2 min ninguna está resuelta todavía


def test_run_sintetico(tmp_path):
    d = _write(tmp_path)
    rep = study49.run(d, tmp_path / "o", hoy=pd.Timestamp("2027-02-01", tz="UTC"), n_boot=200, log=lambda *_: None,
                     exigir_completo=False)
    assert set(rep["hipotesis"]) == {"H49a", "H49b"}
    assert (tmp_path / "o" / "resultado.json").exists()
    for h in rep["hipotesis"].values():
        assert set(h["criterios"]) == {"diferencia_ic", "ev", "min_300"}


def test_no_evalua_si_faltan_dias(tmp_path):
    d = tmp_path / "btc"
    d.mkdir()
    for day in pd.date_range(study49.START, study49.END, freq="D", inclusive="left"):
        if day != pd.Timestamp("2027-01-18", tz="UTC"):  # falta justo el último día
            (d / f"{day:%Y-%m-%d}.jsonl").write_text("", encoding="utf-8")
    assert study49.missing_days(d) == ["2027-01-18"]
    with pytest.raises(SystemExit, match="faltan 1 días"):
        study49.run(d, tmp_path / "o", hoy=pd.Timestamp("2027-01-19", tz="UTC"), log=lambda *_: None)
    assert not (tmp_path / "o").exists()
    (d / "2027-01-18.jsonl").write_text("", encoding="utf-8")
    assert study49.missing_days(d) == []
    assert study49._last_contiguous_end(d) == study49.END
