"""Gran bot (Estudios 63 y 64): metamodelo congelado, filas del registro y evaluación de la confirmación."""

import json
import math

import numpy as np
import pandas as pd
import pytest

from tradingbot.live import gran_bot as gb
from tradingbot.research import study64 as s64

COEF = {m: {"constante": 0.0, "propia": 0.5, "otra": 0.2, "p20": 0.1, "p42": 0.2, "p51": 0.3, "p53": 0.1}
        for m in gb.MONEDAS}


def test_combine_matches_the_logistic_formula():
    op = {"propia": 0.6, "otra": 0.55, "p20": 0.5, "p42": 0.52, "p51": 0.58, "p53": 0.49}
    z = sum(COEF["ETHUSDT"][k] * math.log(v / (1 - v)) for k, v in op.items())
    assert gb.combinar(COEF["ETHUSDT"], op) == pytest.approx(1 / (1 + math.exp(-z)))
    assert gb.combinar(COEF["ETHUSDT"], {k: 0.5 for k in op}) == pytest.approx(0.5)


def test_rows_use_the_right_opinions_and_results():
    t = pd.date_range("2026-11-05 03:00", periods=10, freq="min", tz="UTC")
    op = pd.DataFrame({"okx5_ETHUSDT": 0.62, "okx5_BTCUSDT": 0.45, "p20": 0.5, "p42": 0.5, "p51": 0.6, "p53": 0.5},
                      index=t)
    op.loc[t[9], "p53"] = np.nan  # 03:09 sin SOL: no entra
    from tradingbot.live.okx_eventos import inst_id

    v = t[4] + pd.Timedelta(minutes=1)  # decisión 03:04 → ventana 03:05
    res = {inst_id("ETHUSDT", v): (1, "oficial"), inst_id("BTCUSDT", v): (-1, "reconstruido")}
    filas = gb.filas_dia(op, COEF, res)
    assert len(filas) == 2  # solo 03:04 tiene minuto de decisión de 5 min con las seis opiniones
    eth = [f for f in filas if f["moneda"] == "ETHUSDT"][0]
    btc = [f for f in filas if f["moneda"] == "BTCUSDT"][0]
    assert eth["opiniones"]["propia"] == 0.62 and eth["opiniones"]["otra"] == 0.45
    assert btc["opiniones"]["propia"] == 0.45 and btc["opiniones"]["otra"] == 0.62
    assert eth["resultado"] == 1 and eth["fuente"] == "oficial" and btc["resultado"] == -1
    assert eth["p_base"] == 0.62 and eth["senal_base"] and eth["p_gran"] > 0.5
    assert eth["ventana"] == v.isoformat() and eth["horario_usuario"]


def _registro(tmp_path, gana_gran=0.6, dias=85, seed=0):
    rng = np.random.default_rng(seed)
    reg = tmp_path / "gran5"
    reg.mkdir(parents=True)
    for d in pd.date_range(s64.INICIO, s64.INICIO + pd.Timedelta(days=dias), freq="D", inclusive="left"):
        filas = []
        for j in range(40):
            v = d + pd.Timedelta(minutes=5 * (j + 1))
            sube = rng.uniform() < 0.5
            ok = rng.uniform() < gana_gran
            p_gran = (0.6 if sube else 0.4) if ok else (0.4 if sube else 0.6)
            p_base = 0.6 if j % 2 else 0.5  # la base opera la mitad y acierta al azar
            filas.append({"ventana": v.isoformat(), "moneda": "ETHUSDT" if j % 2 else "BTCUSDT",
                          "instrumento": f"X-{v:%m%d%H%M}-{j}", "p_gran": p_gran, "p_base": p_base,
                          "resultado": 1 if sube else -1, "fuente": "reconstruido", "horario_usuario": False})
        (reg / f"{d:%Y-%m-%d}.jsonl").write_text("".join(json.dumps(x) + "\n" for x in filas))
    return reg


def test_confirmation_passes_only_when_the_big_bot_wins_and_beats_the_base(tmp_path):
    reg = _registro(tmp_path / "a")
    out = tmp_path / "out"
    with pytest.raises(SystemExit, match="no antes"):
        s64.run("enero", reg, out, hoy=pd.Timestamp("2027-01-10", tz="UTC"), n_boot=500)
    rep = s64.run("enero", reg, out, hoy=pd.Timestamp("2027-01-20", tz="UTC"), n_boot=500, log=lambda *_: None)
    assert rep["veredicto"] == "PASA" and all(rep["principal"]["criterios"].values())
    with pytest.raises(SystemExit, match="ya se evaluó"):
        s64.run("enero", reg, out, hoy=pd.Timestamp("2027-01-21", tz="UTC"), n_boot=500)
    reg2 = _registro(tmp_path / "b", gana_gran=0.5, seed=3)
    rep2 = s64.run("enero", reg2, tmp_path / "out2", hoy=pd.Timestamp("2027-01-20", tz="UTC"), n_boot=500,
                   log=lambda *_: None)
    assert not rep2["pasa"] and rep2["veredicto"] == "sigue hasta abril"


def test_freeze_is_one_time(tmp_path, monkeypatch):
    destino = tmp_path / "gran.json"
    destino.write_text("{}")
    with pytest.raises(FileExistsError):
        gb.congelar(destino=destino)


def test_15_minute_rows_use_15_and_5_minute_opinions():
    t = pd.date_range("2026-11-05 03:00", periods=16, freq="min", tz="UTC")
    op = pd.DataFrame({"okx15_ETHUSDT": 0.6, "okx15_BTCUSDT": 0.45, "okx5_ETHUSDT": 0.55, "okx5_BTCUSDT": 0.5,
                       "p20": 0.5, "p42": 0.5, "p51": 0.5, "p53": 0.5}, index=t)
    coef = {m: {"constante": 0.0, **{k: 0.3 for k in gb.OPINIONES_15}} for m in gb.MONEDAS}
    from tradingbot.live.okx_eventos import inst_id

    v = t[14] + pd.Timedelta(minutes=1)  # decisión 03:14 → ventana de 15 min 03:15–03:30
    filas = gb.filas_15(op, coef, {inst_id("ETHUSDT", v, 15): (1, "oficial")})
    assert len(filas) == 2 and filas[0]["instrumento"].startswith(("ETH-UPDOWN-15MIN", "BTC-UPDOWN-15MIN"))
    eth = [f for f in filas if f["moneda"] == "ETHUSDT"][0]
    assert eth["opiniones"]["propia15"] == 0.6 and eth["opiniones"]["otra5"] == 0.5 and eth["resultado"] == 1


def test_blitz_rows_only_where_a_policy_trades():
    t = pd.date_range("2026-11-05 03:00", periods=3, freq="min", tz="UTC")
    op = pd.DataFrame({"p42": [0.5, 0.62, 0.40], "p51": 0.5, "p53": 0.5, "p20": 0.5, "e26_eth": 0.5, "e26_sol": 0.5,
                       "e26_xrp": 0.5, "e26_doge": 0.5}, index=t)
    coef = {"constante": 0.0, **{k: (1.0 if k == "propia" else 0.0) for k in gb.OPINIONES_BLITZ}}
    filas = gb.filas_blitz(op, coef, 0.05, pd.Series([1, 1, 0], index=t))
    assert [f["vela"] for f in filas] == [t[1].isoformat(), t[2].isoformat()]  # 0,5 no opera
    assert filas[0]["senal_base"] and filas[0]["resultado"] == 1 and filas[1]["resultado"] == 0


def test_blitz_and_15_minute_freezes_are_one_time(tmp_path):
    for fn in (gb.congelar_blitz, gb.congelar_okx15):
        destino = tmp_path / f"{fn.__name__}.json"
        destino.write_text("{}")
        with pytest.raises(FileExistsError):
            fn(destino=destino)
