"""Estudio 62: regla del favorito al segundo 60 (BTC 5 min) y salvaguardas."""

import json

import numpy as np
import pandas as pd
import pytest

from tradingbot.live.okx_libro_dentro import inst_id
from tradingbot.research import study62 as s62


def test_favorite_rule():
    assert s62.favorito([[0.72, 10]], [[0.68, 5]]) == (1, 0.72, pytest.approx(0.70))  # «Al alza»
    lado, precio, medio = s62.favorito([[0.32, 10]], [[0.27, 4]])  # «A la baja» a 1 − 0,27
    assert lado == 0 and precio == pytest.approx(0.73) and medio == pytest.approx(0.705)
    assert s62.favorito([[0.75, 10]], [[0.60, 5]]) is None  # diferencial 0,15 > 0,10
    assert s62.favorito([[0.55, 10]], [[0.50, 5]]) is None  # favorito barato (< 0,60)
    assert s62.favorito([[0.95, 10]], [[0.90, 5]]) is None  # demasiado caro (> 0,90)
    assert s62.favorito([[0.80, 0.4], [0.95, 9]], [[0.75, 5]]) is None  # 1 contrato no cabe a ≤ 0,90
    assert s62.favorito([[0.80, 0.4], [0.84, 9]], [[0.75, 5]])[1] == pytest.approx(0.4 * 0.80 + 0.6 * 0.84)


def _datos(tmp_path, acierto, dias=20, seed=0):
    rng = np.random.default_rng(seed)
    d = tmp_path / "dentro"
    d.mkdir(parents=True)
    fotos, res = [], []
    for v in pd.date_range(s62.INICIO, s62.INICIO + pd.Timedelta(days=dias), freq="5min", inclusive="left"):
        inst = inst_id("BTCUSDT", v.to_pydatetime(), 5)
        sube = rng.uniform() < 0.5
        fav_up = rng.uniform() < 0.5
        a, b = ([[0.76, 10]], [[0.72, 10]]) if fav_up else ([[0.28, 10]], [[0.24, 10]])
        gana = rng.uniform() < acierto
        sube = fav_up if gana else not fav_up
        for seg in (60, 150):
            fotos.append({"t": "x", "objetivo": (v + pd.Timedelta(seconds=seg)).isoformat(), "fuente": "github", "dur": 5,
                          "moneda": "BTCUSDT", "inst": inst, "seg": seg, "indice": 1.0, "a": a, "b": b})
        res.append({"inst": inst, "partida": 1, "liquidacion": 1, "resultado": "1" if sube else "2", "vence": 0})
    (d / "2026-11-12_0000.jsonl").write_text("".join(json.dumps(x) + "\n" for x in fotos))
    (d / "2026-11-12_0000_resultados.jsonl").write_text("".join(json.dumps(x) + "\n" for x in res))
    return d


def test_passes_with_a_real_bias_and_fails_without_it(tmp_path):
    rep = s62.evaluar(s62.cargar_fotos(_datos(tmp_path / "a", 0.85)), s62.cargar_resultados(tmp_path / "a" / "dentro"),
                      n_boot=500)
    pr = rep["principal"]
    assert rep["pasa"] and pr["operaciones"] == 20 * 288 and pr["precio_medio"] == pytest.approx(0.76)
    assert pr["ganancia_media"] == pytest.approx(pr["acierto"] - 0.76 - 0.045 * 0.76 * 0.24)
    rep = s62.evaluar(s62.cargar_fotos(_datos(tmp_path / "b", 0.74, seed=1)),
                      s62.cargar_resultados(tmp_path / "b" / "dentro"), n_boot=500)
    assert not rep["pasa"] and rep["veredicto"] == "NO PASA"


def test_one_time_and_not_before_december(tmp_path):
    d = _datos(tmp_path, 0.85, dias=2)
    with pytest.raises(SystemExit, match="no antes"):
        s62.run(d, tmp_path / "out", hoy=pd.Timestamp("2026-12-12", tz="UTC"), n_boot=200)
    rep = s62.run(d, tmp_path / "out", hoy=pd.Timestamp("2026-12-14", tz="UTC"), n_boot=200, log=lambda *_: None)
    assert rep["principal"]["operaciones"] == 2 * 288
    with pytest.raises(SystemExit, match="ya se evaluó"):
        s62.run(d, tmp_path / "out", hoy=pd.Timestamp("2026-12-15", tz="UTC"), n_boot=200)
