"""Estudio 10 (pre-registro en docs/01, commit 41f987b): oro con correlación negativa frente al índice del dólar
y zonas de oferta/demanda en los dos, como en la estrategia de redes que mostró el usuario.

Velas de 15 min (UTC) de oro y de un DXY aproximado (EUR, JPY y GBP con los pesos del ICE renormalizados).
Binaria con entrada 1 min después del cierre de la vela (manual), a 15 y 60 min, 2022-01 → 2025-08.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from ..data import store
from ..data.clean import to_canonical
from ..instruments import get_instrument
from .experiment import git_sha, jsonable
from .metrics import binom_pvalue_greater, block_bootstrap_mean, wilson

START, END = "2022-01-01", "2025-09-01"
DXY_W = {"EURUSD": -0.576, "USDJPY": 0.136, "GBPUSD": -0.119}
DXY_SUM = 0.831
CORR_N, ZONE_N, ATR_N, ZONE_ATR = 20, 96, 14, 0.5
HORIZONS = {"H10a": 15, "H10b": 60}
ALPHA = 0.025  # Bonferroni, 2 hipótesis
POINT = 1e-3  # oro


def _mid(symbol: str, root: Path) -> pd.DataFrame:
    bars, _ = to_canonical(store.load(root, get_instrument(symbol), source="histdata"), fill_gaps=True)
    return bars[(bars.index >= pd.Timestamp("2021-01-01", tz="UTC")) & (bars.index < pd.Timestamp(END, tz="UTC"))]


def dxy_close(fx: dict[str, pd.Series]) -> pd.Series:
    """Cierre de 1 min del DXY aproximado; NaN si falta alguna de las tres monedas."""
    idx = fx["EURUSD"].index.union(fx["USDJPY"].index).union(fx["GBPUSD"].index)
    z = sum(w * np.log(fx[s].reindex(idx)) for s, w in DXY_W.items()) / DXY_SUM
    return np.exp(z)


def to_15m(o, h, l, c) -> pd.DataFrame:
    g = pd.DataFrame({"o": o, "h": h, "l": l, "c": c}).resample("15min", label="left", closed="left")
    return pd.DataFrame({"o": g["o"].first(), "h": g["h"].max(), "l": g["l"].min(), "c": g["c"].last()})


def _atr(b: pd.DataFrame) -> pd.Series:
    prev = b["c"].shift(1)
    tr = pd.concat([b["h"] - b["l"], (b["h"] - prev).abs(), (b["l"] - prev).abs()], axis=1).max(axis=1, skipna=False)
    return tr.rolling(ATR_N, min_periods=ATR_N).mean()


def zones(b: pd.DataFrame) -> pd.DataFrame:
    """Zonas de las 96 velas ANTERIORES a t (24 h) y si la vela t entra en ellas o las respeta."""
    atr = _atr(b)
    lo = b["l"].shift(1).rolling(ZONE_N, min_periods=ZONE_N).min()
    hi = b["h"].shift(1).rolling(ZONE_N, min_periods=ZONE_N).max()
    in_dem = (b["l"] <= lo + ZONE_ATR * atr) & (b["c"] >= lo)
    in_sup = (b["h"] >= hi - ZONE_ATR * atr) & (b["c"] <= hi)
    return pd.DataFrame({"en_demanda": in_dem, "en_oferta": in_sup,
                         "respeta_demanda": (b["l"] <= lo + ZONE_ATR * atr) & (b["c"] > lo) & (b["c"] > b["o"]),
                         "respeta_oferta": (b["h"] >= hi - ZONE_ATR * atr) & (b["c"] < hi) & (b["c"] < b["o"])})


def sides(gold15: pd.DataFrame, dxy15: pd.DataFrame) -> pd.DataFrame:
    corr = gold15["c"].rolling(CORR_N, min_periods=CORR_N).corr(dxy15["c"])
    zg, zd = zones(gold15), zones(dxy15)
    neg = (corr < 0).to_numpy()
    zone_only = np.where(zg["en_demanda"], 1, np.where(zg["en_oferta"], -1, 0))
    full = np.where(neg & zg["en_demanda"] & zd["respeta_oferta"], 1,
                    np.where(neg & zg["en_oferta"] & zd["respeta_demanda"], -1, 0))
    return pd.DataFrame({"completa": full, "solo_zonas": zone_only, "corr": corr}, index=gold15.index)


def simulate(gold1: pd.DataFrame, side: pd.Series, horizon: int) -> pd.DataFrame:
    """Entrada en la apertura del minuto que empieza 1 min después del cierre de la vela de 15 min."""
    o, c = gold1["o"], gold1["c"]
    rows, free_at = [], pd.Timestamp.min.tz_localize("UTC")
    for t, sd in side[side != 0].items():
        close_t = t + pd.Timedelta(minutes=15)
        if close_t < free_at:
            continue
        t_in = close_t + pd.Timedelta(minutes=1)
        t_last = t_in + pd.Timedelta(minutes=horizon - 1)
        entry, exit_ = o.get(t_in, np.nan), c.get(t_last, np.nan)
        if np.isnan(entry) or np.isnan(exit_):
            continue
        free_at = t_last + pd.Timedelta(minutes=1)
        res = int(np.sign(np.round((exit_ - entry) / (POINT / 2)))) * int(sd)
        rows.append({"time": t, "lado": int(sd), "resultado": res, "pnl": 0.0 if res == 0 else (0.85 if res > 0 else -1.0)})
    return pd.DataFrame(rows, columns=["time", "lado", "resultado", "pnl"])


def evaluate(tr: pd.DataFrame, n_boot: int = 2000) -> dict:
    if not len(tr):
        return {"operaciones": 0, "pasa": False, "estado": "insuficiente"}
    nt = tr[tr["resultado"] != 0]
    n, w = len(nt), int((nt["resultado"] > 0).sum())
    lo, hi = wilson(w, n) if n else (float("nan"), float("nan"))
    be = 1 / 1.85
    p = binom_pvalue_greater(w, n, be) if n else 1.0
    week = pd.DatetimeIndex(tr["time"]).strftime("%G-%V")
    b = block_bootstrap_mean(tr["pnl"].to_numpy(), week, n_boot=n_boot, level=1 - ALPHA)
    crit = {"min_300": len(tr) >= 300, "p_bonferroni": p < ALPHA, "wilson": lo > be, "ev_ic_semanal": b["lo"] > 0}
    return {"operaciones": int(len(tr)), "sin_empate": n, "aciertos": w, "acierto": w / n if n else None,
            "lo95": float(lo), "hi95": float(hi), "p": p, "ev": b["mean"], "ev_ic97_5": [b["lo"], b["hi"]],
            "semanas": int(len(set(week))), "criterios": crit, "pasa": all(crit.values()),
            "estado": "insuficiente" if len(tr) < 300 else ("pasa" if all(crit.values()) else "no pasa")}


def filter_effect(zone_tr: pd.DataFrame, full_side: pd.Series, n_boot: int = 2000, seed: int = 12345) -> dict:
    """Sobre las operaciones de la regla de zonas sola: ¿las que el filtro deja pasar aciertan más que las que quita?"""
    tr = zone_tr[zone_tr["resultado"] != 0].copy()
    tr["filtro"] = full_side.reindex(pd.DatetimeIndex(tr["time"])).to_numpy() == tr["lado"].to_numpy()
    tr["gana"] = tr["resultado"] > 0
    keep, drop = tr[tr["filtro"]], tr[~tr["filtro"]]
    week = pd.DatetimeIndex(tr["time"]).strftime("%G-%V").to_numpy()
    uw, inv = np.unique(week, return_inverse=True)
    rng = np.random.default_rng(seed)
    g = tr["gana"].to_numpy()
    f = tr["filtro"].to_numpy()
    kw, kn = np.bincount(inv, weights=g & f, minlength=len(uw)), np.bincount(inv, weights=f, minlength=len(uw))
    dw, dn = np.bincount(inv, weights=g & ~f, minlength=len(uw)), np.bincount(inv, weights=~f, minlength=len(uw))
    idx = rng.integers(0, len(uw), size=(n_boot, len(uw)))
    diff = kw[idx].sum(1) / np.maximum(kn[idx].sum(1), 1) - dw[idx].sum(1) / np.maximum(dn[idx].sum(1), 1)
    losers = ~tr["gana"]
    return {"operaciones_regla_sola": int(len(tr)), "acierto_regla_sola": float(tr["gana"].mean()),
            "pasan_filtro": int(len(keep)), "acierto_pasan": float(keep["gana"].mean()) if len(keep) else None,
            "acierto_quitadas": float(drop["gana"].mean()) if len(drop) else None,
            "diferencia_ic95": [float(np.quantile(diff, 0.025)), float(np.quantile(diff, 0.975))],
            "perdedoras_evitadas": float((losers & ~tr["filtro"]).sum() / max(losers.sum(), 1)),
            "ganadoras_perdidas": float((tr["gana"] & ~tr["filtro"]).sum() / max(tr["gana"].sum(), 1))}


def run(root: Path = Path("data/raw"), out_dir: Path = Path("results/estudio10"), n_boot: int = 2000) -> dict:
    gold1 = _mid("XAUUSD", root)
    fx = {s: _mid(s, root)["c"] for s in DXY_W}
    dxy1 = dxy_close(fx)
    gold15 = to_15m(gold1["o"], gold1["h"], gold1["l"], gold1["c"])
    g = dxy1.resample("15min", label="left", closed="left")  # OHLC de los cierres de 1 min del DXY*
    dxy15 = pd.DataFrame({"o": g.first(), "h": g.max(), "l": g.min(), "c": g.last()}).reindex(gold15.index)
    sd = sides(gold15, dxy15)
    test = sd.index >= pd.Timestamp(START, tz="UTC")
    sd = sd[test]
    res, info = {}, {}
    for h, mins in HORIZONS.items():
        full_tr = simulate(gold1, sd["completa"], mins)
        zone_tr = simulate(gold1, sd["solo_zonas"], mins)
        res[h] = {"vencimiento_min": mins, **evaluate(full_tr, n_boot)}
        info[h] = {"regla_de_zonas_sola": evaluate(zone_tr, n_boot),
                   "efecto_del_filtro": filter_effect(zone_tr, sd["completa"], n_boot)}
    report = {"estudio": "Estudio 10 — oro, correlación y zonas del DXY (pre-registro 41f987b)", "git_sha": git_sha(),
              "periodo": [START, END], "dxy": "aprox. EUR/JPY/GBP con pesos ICE renormalizados",
              "correlacion_media": float(sd["corr"].mean()), "fraccion_corr_negativa": float((sd["corr"] < 0).mean()),
              "resultados": res, "informativo": info, "pasa_alguna": any(r["pasa"] for r in res.values())}
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "resultado.json").write_text(json.dumps(jsonable(report), indent=2, ensure_ascii=False),
                                            encoding="utf-8")
    return report
