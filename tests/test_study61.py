"""Estudio 61: evaluación de Solana en OKX con predicciones sintéticas (sin descargar nada)."""

import numpy as np
import pandas as pd
import pytest

from tradingbot.research import study61 as s61


def _cache(path, acierto5, acierto15, seed=0):
    rng = np.random.default_rng(seed)
    filas = []
    for d, acierto in ((5, acierto5), (15, acierto15)):
        t = pd.date_range("2025-09-01", "2026-10-25", freq=f"{d}min", tz="UTC") - pd.Timedelta(minutes=1)
        p = np.full(len(t), 0.62)  # siempre señal «Al alza» (p − 0,5312 ≥ 0,02)
        y = np.where(rng.uniform(size=len(t)) < acierto, 1.0, -1.0)
        filas.append(pd.DataFrame({"dur": d, "p": p, "y": y}, index=t))
    pd.concat(filas).to_parquet(path)


def test_evaluation_uses_the_okx_cost_and_study54_criteria(tmp_path, monkeypatch):
    monkeypatch.setattr(s61, "CACHE", tmp_path / "sol.parquet")
    monkeypatch.setattr(s61, "load_config", lambda *_: {})
    _cache(s61.CACHE, acierto5=0.58, acierto15=0.50)
    rep = s61.run(out_dir=tmp_path / "out", n_boot=200, log=lambda *_: None)
    a, b = rep["hipotesis"]["H61a"], rep["hipotesis"]["H61b"]
    assert a["equilibrio"] == pytest.approx(s61.COSTO) and a["duracion_min"] == 5
    assert a["pasa"] and all(a["criterios"].values())
    assert not b["pasa"] and not b["criterios"]["p_bonferroni"]
    assert a["ev"] == pytest.approx(a["acierto"] - s61.COSTO, abs=2e-3)
    assert (tmp_path / "out" / "resultado.json").exists()
