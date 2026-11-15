"""Estudio 70: margen 0 el fin de semana en el gran bot de OKX 5 min (pre-registro ebe2874)."""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from tradingbot.research import study64 as s64, study70 as s70
from tradingbot.research.study63 import COSTO


def _registro(tmp_path, gana_finde=0.62, dias=85, seed=0, saltar=None):
    rng = np.random.default_rng(seed)
    reg = tmp_path / "gran5"
    reg.mkdir(parents=True)
    for d in pd.date_range(s64.INICIO, s64.INICIO + pd.Timedelta(days=dias), freq="D", inclusive="left"):
        if saltar is not None and d == saltar:
            continue
        filas = []
        for j in range(40):
            v = d + pd.Timedelta(minutes=5 * (j + 1))
            sube = rng.uniform() < 0.5
            finde = v.dayofweek >= 5
            ok = rng.uniform() < (gana_finde if finde else 0.5)
            pdir = COSTO + 0.01  # dentro de la franja [0; 0,02)
            p = pdir if (sube == ok) else 1 - pdir
            filas.append({"ventana": v.isoformat(), "moneda": "ETHUSDT" if j % 2 else "BTCUSDT",
                          "instrumento": f"X-{v:%m%d%H%M}-{j}", "p_gran": p, "p_base": 0.5,
                          "resultado": 1 if sube else -1, "fuente": "reconstruido", "horario_usuario": False})
        (reg / f"{d:%Y-%m-%d}.jsonl").write_text("".join(json.dumps(x) + "\n" for x in filas))
    return reg


def test_weekend_and_band_definitions():
    v = pd.DatetimeIndex(pd.to_datetime(["2026-11-20 23:55", "2026-11-21 00:00", "2026-11-23 00:00"], utc=True))
    mk = s70.marcas(np.array([0.54, 0.54, 0.54]), np.array([1.0, 1.0, 1.0]), v)
    assert mk["finde"].tolist() == [False, True, False]  # viernes 23:55, sábado 00:00, lunes 00:00 (UTC)
    p = np.array([0.531232, 0.551232, 1 - 0.531232, 0.531])
    mk = s70.marcas(p, np.ones(4), pd.DatetimeIndex([pd.Timestamp("2026-11-21", tz="UTC")] * 4))
    assert mk["banda"].tolist() == [True, False, True, False] and mk["extra"].tolist() == [True, False, True, False]
    assert mk["actual"].tolist() == [False, True, False, False]


def test_confirmation_guards_and_verdicts(tmp_path):
    reg = _registro(tmp_path / "a")
    out = tmp_path / "out"
    with pytest.raises(SystemExit, match="no antes"):
        s70.run("enero", reg, out, hoy=pd.Timestamp("2027-01-10", tz="UTC"), n_boot=300)
    with pytest.raises(SystemExit, match="primero va la mirada de enero"):
        s70.run("abril", reg, out, hoy=pd.Timestamp("2027-04-28", tz="UTC"), n_boot=300)
    rep = s70.run("enero", reg, out, hoy=pd.Timestamp("2027-01-20", tz="UTC"), n_boot=300, log=lambda *_: None)
    assert rep["veredicto"] == "PASA" and rep["extra"]["operaciones"] >= 300
    assert rep["informativo"]["control_entre_semana"]["operaciones"] > 0
    with pytest.raises(SystemExit, match="ya se evaluó"):
        s70.run("enero", reg, out, hoy=pd.Timestamp("2027-01-21", tz="UTC"), n_boot=300)
    with pytest.raises(SystemExit, match="ya pasó en enero"):
        s70.run("abril", reg, out, hoy=pd.Timestamp("2027-04-28", tz="UTC"), n_boot=300)
    reg2 = _registro(tmp_path / "b", gana_finde=0.5, seed=4)
    rep2 = s70.run("enero", reg2, tmp_path / "out2", hoy=pd.Timestamp("2027-01-20", tz="UTC"), n_boot=300,
                   log=lambda *_: None)
    assert not rep2["pasa"] and rep2["veredicto"] == "sigue hasta abril"
    reg3 = _registro(tmp_path / "c", saltar=pd.Timestamp("2026-12-01", tz="UTC"))
    with pytest.raises(SystemExit, match="faltan 1 días"):
        s70.run("enero", reg3, tmp_path / "out3", hoy=pd.Timestamp("2027-01-20", tz="UTC"), n_boot=300)


@pytest.mark.skipif(not Path("results/estudio63/predicciones.parquet").exists(),
                    reason="predicciones de desarrollo del Estudio 63 no versionadas")
def test_development_figures_match_the_preregistration():
    rep = s70.desarrollo(n_boot=10_000)
    ex = rep["extra"]
    assert ex["operaciones"] == 11_051 and ex["acierto"] == pytest.approx(0.5518, abs=1e-4)
    assert ex["ganancia_total"] == pytest.approx(227.355, abs=0.01)
    assert rep["principal"]["limite"] == pytest.approx(137.9, abs=1.0)  # cuantil 5 % por semanas
    assert rep["informativo"]["control_entre_semana"]["acierto"] == pytest.approx(0.5266, abs=1e-4)
