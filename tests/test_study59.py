"""Estudio 59: unión con Polymarket, precio del lado de la señal y criterios."""

import numpy as np
import pandas as pd
import pytest

from tradingbot.research import study59 as s59


def _datos(tmp_path, informado: bool, n=3000, seed=0):
    """Mercado falso: la p del modelo es la probabilidad real. Si `informado`, el mercado cotiza esa misma
    probabilidad (sin ventaja); si no, cotiza 0,50/0,51 siempre (la ventaja del modelo queda entera)."""
    rng = np.random.default_rng(seed)
    datos = tmp_path / "pm"
    datos.mkdir()
    ini = pd.date_range("2026-04-01", periods=n, freq="5min", tz="UTC")
    p = np.clip(rng.normal(0.5, 0.06, n), 0.3, 0.7)
    sube = (rng.uniform(size=n) < p).astype(int)
    pred = []
    for sym, coin in s59.MONEDAS.items():
        cid = [f"{coin}{i}" for i in range(n)]
        markets = pd.DataFrame({"condition_id": cid, "market_start": ini, "outcome": np.where(sube == 1, "Up", "Down")})
        markets.to_parquet(datos / f"{coin}_markets.parquet")
        mid = p if informado else np.full(n, 0.5)
        rows = []
        for k, c in enumerate(cid):
            t0 = int(ini[k].timestamp())
            for off in (0, 10, 30, 60, 120):
                rows.append((c, t0 + off, mid[k] - 0.01, mid[k] + 0.01, 1 - mid[k] - 0.01, 1 - mid[k] + 0.01))
        pd.DataFrame(rows, columns=["condition_id", "t", "bu", "au", "bd", "ad"]).to_parquet(datos / f"{coin}_ticks.parquet")
        pred.append(pd.DataFrame({"simbolo": sym, "dur": 5, "p": p, "y": np.where(sube == 1, 1.0, -1.0)},
                                 index=pd.DatetimeIndex(ini - pd.Timedelta(minutes=1), name="time")))
    pd.concat(pred).to_parquet(tmp_path / "pred.parquet")
    return datos, tmp_path / "pred.parquet"


def test_uninformed_market_leaves_the_edge(tmp_path):
    datos, pred = _datos(tmp_path, informado=False)
    rep = s59.run(datos, pred, tmp_path / "out", n_boot=500, log=lambda *_: None)
    pr = rep["principal"]
    assert pr["precio_medio"] == pytest.approx(0.51)  # compra a la venta del lado de la señal
    assert pr["ganancia_media"] == pytest.approx(pr["acierto"] - 0.51)
    assert rep["pasa"] and rep["coincidencia_polymarket_okx"] == 1.0
    assert rep["logistica"]["coef_modelo"] > 0.5  # el modelo aporta: el mercado no sabe nada


def test_informed_market_removes_the_edge(tmp_path):
    datos, pred = _datos(tmp_path, informado=True, seed=1)
    rep = s59.run(datos, pred, tmp_path / "out", n_boot=500, log=lambda *_: None)
    assert not rep["pasa"] and rep["principal"]["ganancia_media"] < 0.005
    assert rep["correlacion_rangos_p_vs_mercado"]["todas"] > 0.99
