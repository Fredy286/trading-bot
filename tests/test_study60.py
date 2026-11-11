"""Estudio 60: confirmación de 15 min (dos miradas, salvaguardas y criterios)."""

import json

import numpy as np
import pandas as pd
import pytest

from tradingbot.research import study60 as s60


def _registro(tmp_path, acierto=0.62, fin="2027-01-19", por_dia=6, seed=0):
    rng = np.random.default_rng(seed)
    reg = tmp_path / "registro"
    for carpeta in s60.MONEDAS:
        (reg / carpeta).mkdir(parents=True)
        for d in pd.date_range(s60.INICIO, pd.Timestamp(fin, tz="UTC"), freq="D", inclusive="left"):
            rows = [{"ventana": (d + pd.Timedelta(minutes=15 * (2 + 5 * j))).isoformat(), "instrumento": f"X-{d:%m%d}-{j}",
                     "p": 0.6, "ev_accion": 0.07, "horario_usuario": j == 0, "fuente": "reconstruido",
                     "resultado": "gana" if rng.uniform() < acierto else "pierde"} for j in range(por_dia)]
            (reg / carpeta / f"{d:%Y-%m-%d}.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    return reg


def test_passes_with_a_clear_edge_and_is_one_time(tmp_path):
    reg = _registro(tmp_path)
    out = tmp_path / "out"
    with pytest.raises(SystemExit, match="no antes"):
        s60.run("enero", reg, out, hoy=pd.Timestamp("2027-01-18", tz="UTC"), n_boot=500)
    rep = s60.run("enero", reg, out, hoy=pd.Timestamp("2027-01-20", tz="UTC"), n_boot=500, log=lambda *_: None)
    assert rep["veredicto"] == "PASA" and rep["principal"]["operaciones"] == 2 * 85 * 6
    assert rep["principal"]["ganancia_media"] == pytest.approx(rep["principal"]["acierto"] - s60.COSTO)
    with pytest.raises(SystemExit, match="ya se evaluó"):
        s60.run("enero", reg, out, hoy=pd.Timestamp("2027-01-21", tz="UTC"), n_boot=500)
    with pytest.raises(SystemExit, match="ya pasó en enero"):
        s60.run("abril", reg, out, hoy=pd.Timestamp("2027-04-28", tz="UTC"), n_boot=500)


def test_no_edge_waits_for_april_and_missing_days_block(tmp_path):
    reg = _registro(tmp_path, acierto=0.5, seed=2)
    out = tmp_path / "out"
    (reg / "okx15_eth" / "2026-12-01.jsonl").unlink()
    with pytest.raises(SystemExit, match="faltan 1 días"):
        s60.run("enero", reg, out, hoy=pd.Timestamp("2027-01-20", tz="UTC"), n_boot=500)
    (reg / "okx15_eth" / "2026-12-01.jsonl").write_text("")
    rep = s60.run("enero", reg, out, hoy=pd.Timestamp("2027-01-20", tz="UTC"), n_boot=500, log=lambda *_: None)
    assert rep["veredicto"] == "sigue hasta abril" and not rep["pasa"]
