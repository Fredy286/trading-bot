"""Estudios 66 y 67: el apilado en el blitz (con empates) y en OKX 15 min (alineado con 5 min)."""

import numpy as np
import pandas as pd

from tradingbot.research import study66 as s66
from tradingbot.research import study67 as s67

SIG = lambda x: 1 / (1 + np.exp(-x))  # noqa: E731


def test_blitz_stacking_uses_the_informative_opinion_and_handles_ties(tmp_path):
    rng = np.random.default_rng(0)
    t = pd.date_range("2025-09-01", "2026-10-25", freq="20min", tz="UTC", name="time")
    n = len(t)
    a, b = rng.normal(size=n), rng.normal(size=n)
    sube = rng.uniform(size=n) < SIG(0.3 * a + 0.8 * b)
    y = np.where(rng.uniform(size=n) < 0.05, 0.0, np.where(sube, 1.0, -1.0))  # 5 % de empates
    pd.DataFrame({"p": SIG(0.3 * a), "p_ref": 0.5, "y": y, "q": 0.05}, index=t).to_parquet(tmp_path / "p42.parquet")
    fuentes = {}
    for k in ("p51", "p53", "p20", *s66.E26):
        x = SIG(0.8 * b) if k == "p51" else SIG(rng.normal(scale=0.3, size=n))
        pd.DataFrame({"p": x}, index=t).to_parquet(tmp_path / f"{k}.parquet")
        fuentes[k] = tmp_path / f"{k}.parquet"
    rep = s66.run(tmp_path / "out", n_boot=500, log=lambda *_: None, p42=tmp_path / "p42.parquet", fuentes=fuentes)
    assert rep["pasa"] and rep["gran_bot"]["ganancia_total"] > rep["base"]["ganancia_total"]
    assert rep["coeficientes"]["2026-10"]["p51"] > 0.5


def test_15_minute_stacking_aligns_5_and_15_minute_opinions(tmp_path):
    rng = np.random.default_rng(1)
    t15 = pd.date_range("2025-09-01 00:14", "2026-10-25", freq="15min", tz="UTC", name="time")
    t5 = pd.date_range("2025-09-01 00:04", "2026-10-25", freq="5min", tz="UTC", name="time")
    filas = []
    verdad = {}
    for sym in ("ETHUSDT", "BTCUSDT"):
        a = rng.normal(size=len(t15))
        y = np.where(rng.uniform(size=len(t15)) < SIG(0.3 * a), 1.0, -1.0)
        verdad[sym] = (a, y)
        filas.append(pd.DataFrame({"simbolo": sym, "dur": 15, "p": SIG(0.3 * a), "y": y}, index=t15))
        filas.append(pd.DataFrame({"simbolo": sym, "dur": 5, "p": 0.5, "y": 1.0}, index=t5))
    pd.concat(filas).to_parquet(tmp_path / "p54.parquet")
    fuentes = {}
    for k in ("p20", "p42", "p51", "p53"):
        pd.DataFrame({"p": SIG(rng.normal(scale=0.3, size=len(t5)))}, index=t5).to_parquet(tmp_path / f"{k}.parquet")
        fuentes[k] = tmp_path / f"{k}.parquet"
    rep = s67.run(tmp_path / "out", n_boot=500, log=lambda *_: None, p54_path=tmp_path / "p54.parquet", fuentes=fuentes)
    # todas las filas de 15 min encuentran su opinión de 5 min (mismo minuto de decisión)
    meses_prueba = (t15 >= pd.Timestamp("2025-11-01", tz="UTC")).sum()
    assert rep["filas"] == 2 * meses_prueba
    assert not rep["pasa"]  # las opiniones extra son ruido: no hay mejora real
