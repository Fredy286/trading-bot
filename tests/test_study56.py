"""Estudio 56: precio real del libro de OKX para cada señal registrada (precio por lado, criterios y salvaguardas)."""

import json

import numpy as np
import pandas as pd
import pytest

from tradingbot.live.okx_eventos import inst_id
from tradingbot.research import study56 as s56


def test_price_to_buy_one_contract_walks_the_book():
    foto = {"a": [[0.55, 8.0], [0.51, 0.4], [0.52, 13.1]], "b": [[0.48, 13.1], [0.45, 8.0]]}
    p, disp = s56.precio_un_contrato(foto, "Up")
    assert p == pytest.approx(0.4 * 0.51 + 0.6 * 0.52) and disp == pytest.approx(13.5)
    p, disp = s56.precio_un_contrato(foto, "Down")  # «A la baja» cuesta 1 − cada compra de «Al alza»
    assert p == pytest.approx(0.52) and disp == pytest.approx(13.1)
    assert s56.precio_un_contrato({"a": [[0.55, 8.0]], "b": []}, "Up") == (None, 0)
    assert s56.precio_un_contrato({"a": [[0.52, 0.3]], "b": []}, "Up") == (None, pytest.approx(0.3))
    assert s56.precio_un_contrato({"a": [], "b": []}, "Down") == (None, 0)
    assert s56.costo(0.52) == pytest.approx(s56.COSTO_REF)


def _datos(tmp_path, n_semanas=10, por_dia=8, acierto=0.7, fin="2027-01-19", seed=0):
    """Registro con un archivo por día (como el real) y el libro grabado de cada señal: 1 de cada 5 sin foto o con
    error, y 1 de cada 4 con su lado a 0,55 (bloqueada)."""
    rng = np.random.default_rng(seed)
    reg, lib = tmp_path / "registro", tmp_path / "libro"
    lib.mkdir(parents=True)
    filas_libro, k = [], 0
    dias = pd.date_range(s56.INICIO, pd.Timestamp(fin, tz="UTC"), freq="D", inclusive="left")
    for carpeta, sym in s56.MONEDAS.items():
        (reg / carpeta).mkdir(parents=True)
        for d in dias:
            rows = []
            if d < s56.INICIO + pd.Timedelta(weeks=n_semanas):
                for j in range(por_dia):
                    v = d + pd.Timedelta(minutes=5 * (7 + 13 * j))
                    lado = "Up" if j % 2 else "Down"
                    inst = inst_id(sym, v)
                    rows.append({"ventana": v.isoformat(), "instrumento": inst, "lado": lado, "p": 0.57,
                                 "ev_accion": 0.04, "horario_usuario": j == 0,
                                 "resultado": "gana" if rng.uniform() < acierto else "pierde"})
                    k += 1
                    caro = k % 4 == 0
                    a = [[0.55, 8.0]] if (caro and lado == "Up") else [[0.52, 13.1], [0.55, 8.0]]
                    b = [[0.45, 8.0]] if (caro and lado == "Down") else [[0.48, 13.1], [0.45, 8.0]]
                    fotos = [{"seg": s, "a": a, "b": b} for s in (-10, -7, -5, -3)]
                    if k % 5 == 0:
                        continue  # hueco de GitHub
                    if k % 7 == 0:
                        fotos[0] = {"seg": -10, "error": "ConnectionError"}
                    filas_libro.append({"ventana": v.isoformat(), "fuente": "github", sym: {"inst": inst, "fotos": fotos}})
            (reg / carpeta / f"{d:%Y-%m-%d}.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    (lib / "2026-11-09_0003.jsonl").write_text("".join(json.dumps(r) + "\n" for r in filas_libro))
    return reg, lib


def test_evaluate_counts_prices_and_passes_with_a_clear_edge(tmp_path):
    reg, lib = _datos(tmp_path, acierto=0.7)
    sen = s56.cargar_senales(reg, s56.MIRADAS["enero"][0])
    rep = s56.evaluar(sen, s56.cargar_libro(lib), alfa=0.01, n_boot=2000)
    assert rep["senales"] == len(sen) == 2 * 10 * 7 * 8
    cob = rep["cobertura"]
    total = sum(sum(v.values()) for v in cob.values())
    assert total == len(sen) and sum(v["sin foto"] for v in cob.values()) > 0
    pr = rep["principal"]
    assert pr["precio_medio"] == pytest.approx(0.52)
    assert pr["ganancia_media"] == pytest.approx(pr["acierto"] - s56.costo(0.52))
    assert pr["ganancia_con_052"] == pytest.approx(pr["ganancia_media"])
    assert rep["pasa"] and all(pr["criterios"].values())
    assert 0.2 < rep["bloqueadas_por_precio"]["fraccion"] < 0.3
    assert rep["contratos_a_053"]["mediana"] == pytest.approx(13.1)


def test_evaluate_does_not_pass_without_edge(tmp_path):
    reg, lib = _datos(tmp_path, acierto=0.5, seed=3)
    rep = s56.evaluar(s56.cargar_senales(reg, s56.MIRADAS["enero"][0]), s56.cargar_libro(lib), alfa=0.01, n_boot=2000)
    assert not rep["pasa"] and not rep["principal"]["criterios"]["p_menor_alfa"]


def test_run_is_one_time_and_guards_dates_and_missing_days(tmp_path):
    reg, lib = _datos(tmp_path, acierto=0.7)
    out = tmp_path / "salida"
    with pytest.raises(SystemExit, match="no antes"):
        s56.run("enero", reg, lib, out, hoy=pd.Timestamp("2027-01-18", tz="UTC"), n_boot=500)
    with pytest.raises(SystemExit, match="primero va la mirada de enero"):
        s56.run("abril", reg, lib, out, hoy=pd.Timestamp("2027-04-28", tz="UTC"), n_boot=500)
    falta = reg / "okx_btc" / "2026-12-01.jsonl"
    guardado = falta.read_text()
    falta.unlink()
    with pytest.raises(SystemExit, match="faltan 1 días"):
        s56.run("enero", reg, lib, out, hoy=pd.Timestamp("2027-01-20", tz="UTC"), n_boot=500)
    falta.write_text(guardado)
    rep = s56.run("enero", reg, lib, out, hoy=pd.Timestamp("2027-01-20", tz="UTC"), n_boot=500, log=lambda *_: None)
    assert rep["veredicto"] == "PASA" and (out / "enero.json").exists()
    with pytest.raises(SystemExit, match="ya se evaluó"):
        s56.run("enero", reg, lib, out, hoy=pd.Timestamp("2027-01-21", tz="UTC"), n_boot=500)
    with pytest.raises(SystemExit, match="ya pasó en enero"):
        s56.run("abril", reg, lib, out, hoy=pd.Timestamp("2027-04-28", tz="UTC"), n_boot=500)


def test_only_github_recordings_count_and_first_valid_wins(tmp_path):
    v = pd.Timestamp("2026-11-09 00:10", tz="UTC")
    inst = inst_id("ETHUSDT", v)
    malo = {"ventana": v.isoformat(), "fuente": "github",
            "ETHUSDT": {"inst": inst, "fotos": [{"seg": -10, "error": "x"}]}}
    bueno = {"ventana": v.isoformat(), "fuente": "github",
             "ETHUSDT": {"inst": inst, "fotos": [{"seg": -10, "a": [[0.51, 20]], "b": [[0.49, 20]]}]}}
    local = {"ventana": v.isoformat(), "fuente": "local",
             "ETHUSDT": {"inst": inst, "fotos": [{"seg": -10, "a": [[0.40, 20]], "b": [[0.60, 20]]}]}}
    (tmp_path / "a.jsonl").write_text(json.dumps(local) + "\n" + json.dumps(malo) + "\n")
    (tmp_path / "b.jsonl").write_text(json.dumps(bueno) + "\n")
    lib = s56.cargar_libro(tmp_path)
    assert lib[inst]["valida"] and lib[inst]["fotos"][-10]["a"] == [[0.51, 20]]
