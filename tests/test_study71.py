"""Estudio 71: apoyo del gran bot de 15 min al contrato de 5 min de OKX, entre semana (pre-registro ebe2874)."""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from tradingbot.research import study64 as s64, study71 as s71
from tradingbot.research.study63 import COSTO


def _df5(rows):
    df = pd.DataFrame(rows)
    df["ventana"] = pd.to_datetime(df["ventana"], utc=True)
    return df.set_index("ventana")


def test_rule_only_aligned_weekday_same_side_and_band():
    banda = COSTO + 0.01
    r5 = [  # p_gran de 5 min en la franja, al alza
        {"ventana": "2026-11-18 10:15", "moneda": "ETHUSDT", "p_gran": banda, "resultado": 1},   # cumple todo
        {"ventana": "2026-11-18 10:20", "moneda": "ETHUSDT", "p_gran": banda, "resultado": 1},   # no alineada
        {"ventana": "2026-11-21 10:15", "moneda": "ETHUSDT", "p_gran": banda, "resultado": 1},   # sábado
        {"ventana": "2026-11-18 10:30", "moneda": "ETHUSDT", "p_gran": 1 - banda, "resultado": 1},  # otro lado
        {"ventana": "2026-11-18 10:45", "moneda": "ETHUSDT", "p_gran": COSTO + 0.03, "resultado": -1},  # ya opera solo
        {"ventana": "2026-11-18 10:15", "moneda": "BTCUSDT", "p_gran": banda, "resultado": -1},  # 15 min de BTC sin señal
    ]
    r15 = pd.DataFrame([
        {"ventana": "2026-11-18 10:15", "moneda": "ETHUSDT", "p_gran": 0.60, "senal_gran": True},
        {"ventana": "2026-11-21 10:15", "moneda": "ETHUSDT", "p_gran": 0.60, "senal_gran": True},
        {"ventana": "2026-11-18 10:30", "moneda": "ETHUSDT", "p_gran": 0.60, "senal_gran": True},
        {"ventana": "2026-11-18 10:45", "moneda": "ETHUSDT", "p_gran": 0.60, "senal_gran": True},
        {"ventana": "2026-11-18 10:15", "moneda": "BTCUSDT", "p_gran": 0.54, "senal_gran": False},
    ])
    r15["ventana"] = pd.to_datetime(r15["ventana"], utc=True)
    j = s71.unir(_df5(r5), r15.set_index("ventana"))
    toma, g = s71.regla(j)
    assert int(toma.sum()) == 1
    assert j[toma].index.tolist() == [pd.Timestamp("2026-11-18 10:15", tz="UTC")]
    assert j[toma]["moneda"].tolist() == ["ETHUSDT"] and g[toma][0] == pytest.approx(1 - COSTO)


def _registros(tmp_path, dias=85):
    rng = np.random.default_rng(1)
    r5, r15 = tmp_path / "gran5", tmp_path / "gran15"
    r5.mkdir(parents=True)
    r15.mkdir(parents=True)
    for d in pd.date_range(s64.INICIO, s64.INICIO + pd.Timedelta(days=dias), freq="D", inclusive="left"):
        f5, f15 = [], []
        for k in range(24):
            v = d + pd.Timedelta(minutes=15 * k)
            sube = rng.uniform() < 0.5
            ok = rng.uniform() < 0.62
            lado_ok = sube == ok
            p5 = COSTO + 0.01 if lado_ok else 1 - (COSTO + 0.01)
            p15 = 0.60 if lado_ok else 0.40
            f5.append({"ventana": v.isoformat(), "moneda": "ETHUSDT", "instrumento": f"E5-{v:%m%d%H%M}",
                       "p_gran": p5, "p_base": 0.5, "resultado": 1 if sube else -1, "fuente": "reconstruido",
                       "horario_usuario": False})
            f15.append({"ventana": v.isoformat(), "moneda": "ETHUSDT", "instrumento": f"E15-{v:%m%d%H%M}",
                        "p_gran": p15, "senal_gran": True, "resultado": None})
        (r5 / f"{d:%Y-%m-%d}.jsonl").write_text("".join(json.dumps(x) + "\n" for x in f5))
        (r15 / f"{d:%Y-%m-%d}.jsonl").write_text("".join(json.dumps(x) + "\n" for x in f15))
    return r5, r15


def test_sequence_after_study_70(tmp_path):
    r5, r15 = _registros(tmp_path)
    s70dir, out = tmp_path / "e70", tmp_path / "e71"
    hoy = pd.Timestamp("2027-01-20", tz="UTC")
    with pytest.raises(SystemExit, match="primero va la mirada de enero del Estudio 70"):
        s71.run("enero", r5, r15, out, s70dir, hoy=hoy, n_boot=300)
    s70dir.mkdir()
    (s70dir / "enero.json").write_text(json.dumps({"pasa": False}))
    rep = s71.run("enero", r5, r15, out, s70dir, hoy=hoy, n_boot=300, log=lambda *_: None)
    assert rep["veredicto"].startswith("NO EVALUADA") and not rep["evaluada"]
    (out / "enero.json").unlink()
    (s70dir / "enero.json").write_text(json.dumps({"pasa": True}))
    rep = s71.run("enero", r5, r15, out, s70dir, hoy=hoy, n_boot=300, log=lambda *_: None)
    assert rep["evaluada"] and rep["veredicto"] == "PASA" and rep["operaciones"]["operaciones"] >= 300
    with pytest.raises(SystemExit, match="ya pasó en enero"):
        s71.run("abril", r5, r15, out, s70dir, hoy=pd.Timestamp("2027-04-28", tz="UTC"), n_boot=300)


@pytest.mark.skipif(not (Path("results/estudio63/predicciones.parquet").exists()
                         and Path("results/estudio54/predicciones.parquet").exists()),
                    reason="predicciones de desarrollo no versionadas")
def test_development_figures_match_the_preregistration():
    rep = s71.desarrollo(n_boot=10_000)
    op = rep["operaciones"]
    assert op["operaciones"] == 4_188 and op["acierto"] == pytest.approx(0.5506, abs=1e-4)
    assert op["ganancia_total"] == pytest.approx(81.2, abs=0.05)
    assert rep["principal"]["limite"] == pytest.approx(14.6, abs=1.5)
