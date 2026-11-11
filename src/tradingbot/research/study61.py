"""Estudio 61 (pre-registro 4760414, docs/01): Solana en los event contracts de OKX, a 5 y 15 min (desarrollo).

La receta del Estudio 54 sin cambios, con los datos de SOL: velas de 1 min y de 1 s de Binance SOLUSDT, cierres de
Bybit y OKX y el índice `SOL-USDT` de OKX (con el que liquidan los contratos). Mes a mes del 2025-09 al 2026-10-25.
Costo 0,5312 por acción (0,52 + comisión del tomador); se opera si p − 0,5312 ≥ 0,02.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import bolsas, study51, study54
from .experiment import git_sha, jsonable, load_config
from .features import FEATURES, compute_features
from .study3 import spot_bars
from .study16 import partial_features
from .study20 import TEST_END, TEST_START
from .study41 import composite
from .study42 import comp_features

SYMBOL = "SOLUSDT"
INDICE = "SOL-USDT"
SEG = Path("data/processed/estudio26/SOLUSDT/1s")
TAB = Path("data/processed/estudio26/SOLUSDT/tabla.parquet")
M1 = Path("data/processed/estudio26/SOLUSDT/1m")
COSTO = 0.52 + 0.045 * 0.52 * 0.48  # 0,5312
ALFA = 0.025
HIP = {5: "H61a", 15: "H61b"}
CACHE = Path("data/processed/estudio61/SOLUSDT.parquet")


def sec_close(ym: str) -> pd.Series:
    f = SEG / f"{ym}.parquet"
    return pd.read_parquet(f, columns=["c"])["c"] if f.exists() else pd.Series(dtype=float)


def index_closes() -> pd.Series:
    x = pd.concat([bolsas.okx_index_month(INDICE, m) for m in study54._months()]).sort_index()
    return x[~x.index.duplicated(keep="last")]


def run_symbol(cfg, log=print, durs=(5, 15)) -> dict:
    """Lo mismo que `study54.run_symbol`, con las fuentes de SOL."""
    spot = study51.minute_bars(symbol=SYMBOL, m1=M1)
    bars = spot_bars(spot[~spot.index.duplicated(keep="last")].sort_index())
    data_start = pd.Timestamp(TEST_START, tz="UTC") - pd.DateOffset(months=12) - pd.Timedelta(days=7)
    bars = bars[(bars.index >= data_start) & (bars.index < pd.Timestamp(TEST_END, tz="UTC"))]
    idx = bars.index
    tab = pd.read_parquet(TAB).reindex(idx)
    cl = {v: x for v, x in study51.closes(symbol=SYMBOL).items() if v in ("binance", "bybit", "okx")}
    prev = compute_features(bars).shift(1)
    vol_prev = np.exp(prev["lvol60"])
    X = pd.concat([prev[FEATURES], partial_features(tab, bars["o"], vol_prev, study54.K),
                   comp_features(composite(cl), cl["binance"], vol_prev, idx)], axis=1)
    ok = X.notna().all(axis=1).to_numpy()
    ix = index_closes()
    labels = {d: np.full(len(idx), np.nan) for d in durs}
    months = study54._months(data_start.strftime("%Y-%m"), "2026-10")
    ym_arr = np.asarray(idx.strftime("%Y-%m"))
    for k, ym in enumerate(months):
        rows = np.flatnonzero(ym_arr == ym)
        if not len(rows):
            continue
        cur = sec_close(ym)
        nxt = sec_close(months[k + 1]).iloc[:3600] if k + 1 < len(months) else cur.iloc[:0]
        sec = pd.concat([cur, nxt]).sort_index()
        sec = sec[~sec.index.duplicated(keep="last")]
        if sec.empty:
            continue
        for d in durs:
            labels[d][rows] = study54.settle_labels(idx[rows], d, ix, bars["c"], sec.index, sec.to_numpy(float))
        log(f"  {SYMBOL} {ym}: {len(rows):,} minutos con etiqueta")
    out = {}
    for d in durs:
        log(f"Walk-forward {SYMBOL}, contratos de {d} min:")
        p = study54.walk_forward(X, labels[d], ok, idx, d, cfg, log)
        grid = ((idx.minute + 1) % d) == 0
        sel = ~np.isnan(p) & grid
        out[d] = {"p": p[sel], "y": labels[d][sel], "t": idx[sel]}
    return out


def run_symbol_cached(cfg, log=print) -> dict:
    if CACHE.exists():
        df = pd.read_parquet(CACHE)
        return {int(d): {"p": g["p"].to_numpy(), "y": g["y"].to_numpy(), "t": pd.DatetimeIndex(g.index)}
                for d, g in df.groupby("dur")}
    r = run_symbol(cfg, log)
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    pd.concat([pd.DataFrame({"dur": d, "p": x["p"], "y": x["y"]}, index=x["t"]) for d, x in r.items()]).to_parquet(CACHE)
    return r


def _coincidencia(t: pd.DatetimeIndex, p: np.ndarray, d: int) -> dict:
    """Informativo: de las señales de SOL, qué fracción cae en la misma ventana que una señal de ETH o BTC."""
    f = Path("results/estudio54/predicciones.parquet")
    if not f.exists():
        return {}
    o = pd.read_parquet(f)
    o = o[o["dur"] == d]
    pdir = np.maximum(o["p"], 1 - o["p"])
    otras = set(o.index[(pdir - COSTO >= 0.02).to_numpy()])
    mine = t[(np.maximum(p, 1 - p) - COSTO >= 0.02)]
    return {"senales_sol": int(len(mine)), "con_senal_eth_o_btc": float(np.mean([x in otras for x in mine])) if len(mine) else None}


def run(out_dir: Path = Path("results/estudio61"), n_boot: int = 1000, log=print) -> dict:
    cfg = load_config("config/research.toml")  # solo se lee
    r = run_symbol_cached(cfg, log)
    rep = {"estudio": "Estudio 61 — Solana en los contratos de OKX, 5 y 15 min (pre-registro 4760414)",
           "git_sha": git_sha(), "periodo_prueba": [TEST_START, TEST_END], "costo": COSTO, "hipotesis": {},
           "informativo": {}}
    for d, x in sorted(r.items()):
        ev = study54.evaluate(x["p"], x["y"], x["t"], precio=COSTO, comision=0.0, n_boot=n_boot)
        crit = {"min_300": ev["operaciones"] >= 300, "p_bonferroni": ev["p"] < ALFA, "wilson": ev["lo95"] > COSTO,
                "ev_ic": (ev["ev_ic"][0] or -1) > 0, "meses_60": ev["meses_ev_positivo"] >= 0.6}
        ev.update({"criterios": crit, "pasa": all(crit.values()), "duracion_min": d})
        rep["hipotesis"][HIP[d]] = ev
        user = (x["t"].hour >= 2) & (x["t"].hour < 6)
        info = {"horario_usuario": study54.evaluate(np.where(user, x["p"], 0.5), x["y"], x["t"], precio=COSTO,
                                                    comision=0.0, n_boot=200, level=0.95),
                "umbrales": {str(u): study54.evaluate(x["p"], x["y"], x["t"], umbral=u, precio=COSTO, comision=0.0,
                                                      n_boot=200, level=0.95) for u in (0.55, 0.57, 0.60)},
                "coincidencia": _coincidencia(x["t"], x["p"], d), "tasa_sube": float(np.nanmean(x["y"] > 0))}
        for v in [info["horario_usuario"], *info["umbrales"].values()]:
            v.pop("mensual", None)
        rep["informativo"][HIP[d]] = info
        log(f"{HIP[d]} SOL {d} min: pasa={ev['pasa']} | {ev['operaciones']} ops ({ev['por_dia']:.1f}/día), acierto "
            f"{ev['acierto']} [{ev['lo95']:.4f}], EV/acción {ev['ev']} | {crit}")
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "resultado.json").write_text(json.dumps(jsonable(rep), indent=2, ensure_ascii=False) + "\n",
                                            encoding="utf-8")
    return rep
