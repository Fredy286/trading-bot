"""Estudio 63: el metamodelo solo usa el pasado y mejora cuando otra opinión trae información."""

import numpy as np
import pandas as pd
import pytest

from tradingbot.research import study63 as s63


def _fuentes(tmp_path, informativa: bool, seed=0):
    """Cada moneda tiene su propia verdad y una opinión propia calibrada. Si `informativa`, p42 trae información
    extra sobre ETH que la opinión propia no tiene; si no, las demás opiniones son ruido."""
    rng = np.random.default_rng(seed)
    t = pd.date_range("2025-09-01", "2026-10-25", freq="30min", tz="UTC", name="time")
    n = len(t)
    sig = lambda x: 1 / (1 + np.exp(-x))  # noqa: E731
    p54, extra = [], None
    for sym in s63.MONEDAS:
        a, b = rng.normal(size=n), rng.normal(size=n)  # a: lo que ve el modelo propio; b: lo que solo ve p42
        verdad = 0.4 * a + (0.9 * b if informativa else 0.0)
        y = np.where(rng.uniform(size=n) < sig(verdad), 1.0, -1.0)
        propia = sig(0.4 * a) if not informativa else sig(0.4 * a)
        p54.append(pd.DataFrame({"simbolo": sym, "dur": 5, "p": propia, "y": y}, index=t))
        if sym == "ETHUSDT":
            extra = sig(0.9 * b) if informativa else sig(rng.normal(scale=0.3, size=n))
    pd.concat(p54).to_parquet(tmp_path / "p54.parquet")
    fuentes = {}
    for k in ("p20", "p42", "p51", "p53"):
        x = extra if k == "p42" else sig(rng.normal(scale=0.3, size=n))
        pd.DataFrame({"p": x}, index=t).to_parquet(tmp_path / f"{k}.parquet")
        fuentes[k] = tmp_path / f"{k}.parquet"
    return tmp_path / "p54.parquet", fuentes


def test_meta_model_beats_the_base_when_another_opinion_is_informative(tmp_path, monkeypatch):
    p54, fuentes = _fuentes(tmp_path, informativa=True)
    monkeypatch.setattr(s63, "P54", p54)
    monkeypatch.setattr(s63, "FUENTES", fuentes)
    rep = s63.run(tmp_path / "out", n_boot=500, log=lambda *_: None)
    assert rep["pasa"] and rep["principal"]["delta_ganancia"] > 0
    assert rep["por_moneda"]["ETHUSDT"]["delta_ganancia"] > 0 and rep["logloss"]["delta"] < 0
    c = rep["coeficientes"]["ETHUSDT"]["2026-10"]
    assert c["p42"] > 0.5 and abs(c["p20"]) < 0.3  # aprende que la opinión útil es p42


def test_no_gain_from_noise_and_training_uses_only_the_past(tmp_path, monkeypatch):
    p54, fuentes = _fuentes(tmp_path, informativa=False, seed=1)
    monkeypatch.setattr(s63, "P54", p54)
    monkeypatch.setattr(s63, "FUENTES", fuentes)
    rep = s63.run(tmp_path / "out", n_boot=500, log=lambda *_: None)
    assert not rep["pasa"]
    # el primer mes de prueba es 2025-11: se entrena solo con 2025-09 y 2025-10
    df = s63.tabla("ETHUSDT", pd.read_parquet(p54), {k: pd.read_parquet(f)["p"] for k, f in fuentes.items()})
    res, coefs = s63.walk_forward(df)
    assert res.index.min() >= pd.Timestamp("2025-11-01", tz="UTC") and set(coefs) == set(s63.PRUEBA)
