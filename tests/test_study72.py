"""Estudio 72: capa de vetos D1 (tendencia de 60 min) y D2 (apertura de Nueva York) (pre-registro defc48c)."""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from tradingbot.research import study72 as s72

T = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731
SIEMPRE = {"zona": "UTC", "abre": {"dia": 0, "hora": "00:00"}, "cierra": {"dia": 6, "hora": "23:59"}, "pausas": []}


def _cierres():
    idx = pd.date_range(s72.INICIO - pd.Timedelta(days=2), T("2027-07-28"), freq="min", inclusive="left")
    k = np.arange(len(idx))
    return pd.Series(100 * np.exp(0.002 * np.sin(2 * np.pi * k / 240)), index=idx)


C = _cierres()


def test_trend_uses_only_closed_candles():
    t = pd.DatetimeIndex([T("2026-11-18 12:00")])
    base = s72.tendencia60(C, t)[0]
    a = C.copy()
    a.loc[T("2026-11-18 12:00")] = 1e9  # la vela en curso no cuenta
    assert s72.tendencia60(a, t)[0] == base
    b = C.copy()
    b.loc[T("2026-11-18 11:59")] = 1e9  # la vela t−1 sí
    assert s72.tendencia60(b, t)[0] == 1
    assert np.isnan(s72.tendencia60(C.drop(T("2026-11-18 10:59")), t)[0])


def test_new_york_open_with_daylight_saving():
    v = pd.DatetimeIndex([T("2026-10-30 13:28"), T("2026-10-30 13:29"), T("2026-10-30 14:58"), T("2026-10-30 14:59"),
                          T("2026-11-02 14:29"), T("2026-11-02 13:29"), T("2026-11-07 14:29")])
    # 30-oct (viernes, horario de verano): 9:30 ET = 13:30 UTC; 2-nov (lunes, sin verano): 9:30 ET = 14:30 UTC
    assert s72.apertura_ny(v + pd.Timedelta(minutes=1)).tolist() == [False, True, True, False, True, False, False]


def test_vetoes_and_holm():
    v = pd.DatetimeIndex([T("2026-11-21 03:00")] * 4)  # sábado: D2 nunca
    out = s72.vetos(v, np.array([1, -1, 1, 1]), np.array([1.0, 1.0, 0.0, np.nan]))
    assert out["D1"].tolist() == [True, False, False, False] and out["veto"].tolist() == out["D1"].tolist()
    assert s72.holm({"H72a": 0.004, "H72b": 0.03}, 0.01, 2) == {"H72a": True, "H72b": False}
    assert s72.holm({"H72a": 0.004, "H72b": 0.009}, 0.01, 2) == {"H72a": True, "H72b": True}
    assert s72.holm({"H72a": None, "H72b": 0.006}, 0.01, 2) == {"H72a": False, "H72b": False}


def _registros(tmp_path, fin=T("2027-01-19"), n=30, malo=0.30, saltar=None, seed=0):
    rng = np.random.default_rng(seed)
    rb, r15 = tmp_path / "blitz", tmp_path / "gran15"
    rb.mkdir(parents=True)
    r15.mkdir(parents=True)
    for d in pd.date_range(s72.INICIO, fin, freq="D", inclusive="left"):
        if saltar is not None and d == saltar:
            continue
        velas = d + pd.to_timedelta(np.sort(rng.choice(1440, n, replace=False)), unit="min")
        tend = s72.tendencia60(C, velas)
        fb = []
        for t, tr in zip(velas, tend):
            lado = 1 if rng.uniform() < 0.5 else -1
            gana = rng.uniform() < (malo if lado == tr else 0.6)
            fb.append({"vela": t.isoformat(), "lado": "CALL" if lado > 0 else "PUT", "p": 0.56,
                       "resultado": "gana" if gana else "pierde"})
        (rb / f"{d:%Y-%m-%d}.jsonl").write_text("".join(json.dumps(x) + "\n" for x in fb))
        ven = d + pd.to_timedelta(15 * np.arange(1, 96, 3), unit="min")
        f15 = []
        for j, v in enumerate(ven):
            tr = s72.tendencia60(C, pd.DatetimeIndex([v - pd.Timedelta(minutes=1)]))[0]
            lado = 1 if rng.uniform() < 0.5 else -1
            sube = (lado == 1) == (rng.uniform() < (malo if lado == tr else 0.6))
            f15.append({"ventana": v.isoformat(), "moneda": "ETHUSDT" if j % 2 else "BTCUSDT",
                        "instrumento": f"I-{v:%m%d%H%M}-{j}", "p_gran": 0.6 if lado > 0 else 0.4, "senal_gran": True,
                        "resultado": 1 if sube else -1})
        (r15 / f"{d:%Y-%m-%d}.jsonl").write_text("".join(json.dumps(x) + "\n" for x in f15))
    return rb, r15


def test_looks_guards_and_verdicts(tmp_path):
    rb, r15 = _registros(tmp_path / "a")
    out = tmp_path / "out"
    kw = dict(n_boot=500, cierres=lambda s: C, horario=SIEMPRE, log=lambda *_: None)
    with pytest.raises(SystemExit, match="no antes"):
        s72.run("enero", rb, r15, out, hoy=T("2027-01-10"), **kw)
    with pytest.raises(SystemExit, match="primero va la mirada de enero"):
        s72.run("abril", rb, r15, out, hoy=T("2027-04-28"), **kw)
    rep = s72.run("enero", rb, r15, out, hoy=T("2027-01-20"), **kw)
    assert rep["hipotesis"]["H72a"]["veredicto"] == "PASA" and rep["hipotesis"]["H72b"]["veredicto"] == "PASA"
    assert rep["hipotesis"]["H72a"]["n_vetadas"] >= 100
    with pytest.raises(SystemExit, match="ya se evaluó"):
        s72.run("enero", rb, r15, out, hoy=T("2027-01-21"), **kw)
    with pytest.raises(SystemExit, match="ya pasaron"):
        s72.run("abril", rb, r15, out, hoy=T("2027-04-28"), **kw)
    rb2, r152 = _registros(tmp_path / "b", malo=0.6, seed=3)  # sin efecto
    rep2 = s72.run("enero", rb2, r152, tmp_path / "out2", hoy=T("2027-01-20"), **kw)
    assert not rep2["hipotesis"]["H72a"]["pasa"] and rep2["hipotesis"]["H72a"]["veredicto"] == "sigue en la próxima mirada"
    rb3, r153 = _registros(tmp_path / "c", n=2, seed=5)  # pocas señales del blitz
    rep3 = s72.run("enero", rb3, r153, tmp_path / "out3", hoy=T("2027-01-20"), **kw)
    assert rep3["hipotesis"]["H72a"]["veredicto"].startswith("SIN CONCLUSIÓN")
    rb4, r154 = _registros(tmp_path / "d", saltar=T("2026-12-01"))
    with pytest.raises(SystemExit, match="faltan 1 días"):
        s72.run("enero", rb4, r154, tmp_path / "out4", hoy=T("2027-01-20"), **kw)


def test_blitz_counts_only_iq_open_hours(tmp_path):
    rb, r15 = _registros(tmp_path / "a")
    rep = s72.run("enero", rb, r15, tmp_path / "o", hoy=T("2027-01-20"), n_boot=200, cierres=lambda s: C,
                  log=lambda *_: None)  # horario del repo (prudente): fuera el fin de semana
    total = s72.cargar_blitz(rb, T("2027-01-19"))
    assert rep["hipotesis"]["H72a"]["senales"]["operaciones"] < len(total)
    assert rep["hipotesis"]["H72a"]["horario_iq"]["cierra"]["dia"] == 4


@pytest.mark.skipif(not (Path("results/estudio42/predicciones.parquet").exists()
                         and Path("results/estudio54/predicciones.parquet").exists()
                         and Path("data/raw/estudio3/BTCUSDT/spot").exists()),
                    reason="predicciones o velas de desarrollo no versionadas")
def test_development_figures_match_the_preregistration():
    rep = s72.desarrollo(n_boot=10_000)
    a, b = rep["H72a"], rep["H72b"]
    assert a["senales"]["operaciones"] == 7_979 and a["n_vetadas"] == 1_722
    assert a["suma_vetadas"] == pytest.approx(-133.56, abs=0.01) and a["p"] < 0.01
    assert a["resto"]["acierto_sin_empates"] == pytest.approx(0.5589, abs=1e-4)
    assert b["n_vetadas"] == 3_273 and b["suma_vetadas"] == pytest.approx(-58.72, abs=0.01)
