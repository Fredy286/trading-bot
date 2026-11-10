"""Estudio 58: sello, definición de M5 y prueba con datos sintéticos (nunca con el registro real)."""

import json

import numpy as np
import pandas as pd
import pytest

from tradingbot.research import study58


def _write(tmp_path, n=6000, gap=0.06, seed=0):
    rng = np.random.default_rng(seed)
    t = pd.date_range("2026-10-26", periods=n, freq="7min", tz="UTC")
    m5 = study58.entry_m5(t)
    win = rng.random(n) < np.where(m5, 0.56 - gap, 0.56)
    res = np.where(rng.random(n) < 0.05, "empate", np.where(win, "gana", "pierde"))
    d = tmp_path / "btc"
    d.mkdir()
    with open(d / "x.jsonl", "w", encoding="utf-8") as f:
        for ti, r in zip(t, res):
            f.write(json.dumps({"vela": ti.isoformat(), "resultado": str(r), "p": 0.61, "umbral_060": True,
                                "modelo": "m"}) + "\n")
    return d


def test_entrada_m5_es_el_minuto_siguiente():
    t = pd.DatetimeIndex(["2026-11-01 10:04", "2026-11-01 10:05", "2026-11-01 10:59", "2026-11-01 10:14"], tz="UTC")
    assert study58.entry_m5(t).tolist() == [True, False, True, True]
    assert study58.entry_quarter(t).tolist() == [False, False, True, True]


def test_sellado_no_evalua(tmp_path):
    with pytest.raises(SystemExit, match="sellado"):
        study58.run(tmp_path, tmp_path / "o", hoy=pd.Timestamp("2027-01-18", tz="UTC"))


def test_faltan_dias_no_evalua(tmp_path):
    d = tmp_path / "btc"
    d.mkdir()
    with pytest.raises(SystemExit, match="faltan"):
        study58.run(d, tmp_path / "o", hoy=pd.Timestamp("2027-01-20", tz="UTC"), log=lambda *_: None)
    assert not (tmp_path / "o").exists()


def test_detecta_brecha_sintetica(tmp_path):
    d = _write(tmp_path, gap=0.08)
    rep = study58.run(d, tmp_path / "o", hoy=pd.Timestamp("2027-02-01", tz="UTC"), n_boot=300,
                      log=lambda *_: None, exigir_completo=False)
    h = rep["H58"]
    assert h["D"] > 0 and h["criterios"]["p"] and h["criterios"]["min_500"]
    assert (tmp_path / "o" / "resultado.json").exists()


def test_sin_brecha_no_pasa_normalmente(tmp_path):
    d = _write(tmp_path, gap=-0.04, seed=1)
    rep = study58.run(d, tmp_path / "o", hoy=pd.Timestamp("2027-02-01", tz="UTC"), n_boot=300,
                      log=lambda *_: None, exigir_completo=False)
    assert not rep["H58"]["pasa"]
