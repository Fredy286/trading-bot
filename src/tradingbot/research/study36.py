"""Estudio 36 (pre-registro en docs/01, commit 767a0b9): reversión nocturna con velas de 1 min de precio medio de Deriv
(feed de un bróker), 19 pares, 2026-04 → 2026-09, entrada en la apertura de la vela t (L = 0) y salida al cierre de la
vela del vencimiento. Comparación con las mismas reglas sobre las velas de HistData (Estudio 27).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from ..live.nocturna import PAIRS, DerivFeed
from .experiment import git_sha, jsonable
from .metrics import binom_pvalue_greater, wilson
from .study22 import BE
from .study27 import seconds
from .study34 import band, one_at_a_time

MONTHS = ("2026-04", "2026-05", "2026-06", "2026-07", "2026-08", "2026-09")
WORK = Path("data/raw/deriv_velas")
VARIANTS = {"H36": (20, 2.0, 3), "fuerte": (30, 2.5, 5)}


def deriv_month(pair: str, ym: str, feed: DerivFeed, work: Path = WORK) -> pd.DataFrame:
    """Velas de 1 min de Deriv entre las 19:30 y las 00:10 UTC de cada día del mes (caché por mes)."""
    f = Path(work) / pair / f"{ym}.parquet"
    if f.exists():
        return pd.read_parquet(f)
    parts = []
    start = pd.Timestamp(ym + "-01", tz="UTC")
    for d in pd.date_range(start, start + pd.offsets.MonthBegin(1), freq="D", inclusive="left"):
        a = int((d + pd.Timedelta(hours=19, minutes=30)).timestamp())
        b = int((d + pd.Timedelta(hours=24, minutes=10)).timestamp())
        r = feed._call({"ticks_history": f"frx{pair}", "style": "candles", "granularity": 60, "count": 5000,
                        "start": a, "end": b})
        c = pd.DataFrame(r.get("candles", []))
        if len(c):
            c = c[(c["epoch"] >= a) & (c["epoch"] <= b)]
            parts.append(c)
    df = pd.concat(parts) if parts else pd.DataFrame(columns=["epoch", "open", "high", "low", "close"])
    df = df.drop_duplicates("epoch").set_index("epoch").sort_index()
    df.index = pd.to_datetime(df.index, unit="s", utc=True)
    df = df[["open", "high", "low", "close"]].astype(float).set_axis(["o", "h", "l", "c"], axis=1)
    f.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(f)
    print(f"  {pair} {ym}: {len(df):,} velas", flush=True)
    return df


def trades(bars: pd.DataFrame, n: int, k: float, dur: int, pair: str) -> pd.DataFrame:
    """Entrada en la apertura de la vela t, salida en el cierre de la vela t + dur − 1 (velas de 1 min)."""
    bars = bars.reindex(pd.date_range(bars.index[0], bars.index[-1], freq="min", tz="UTC"))
    s = band(bars, n, k)
    s = s[(s.index >= pd.Timestamp(MONTHS[0] + "-01", tz="UTC"))]
    s = s[one_at_a_time(s.index, dur)]
    o = bars["o"].reindex(s.index).to_numpy()
    c = bars["c"].reindex(s.index + pd.Timedelta(minutes=dur - 1)).to_numpy()
    d = c - o
    res = np.where(np.isnan(d), np.nan, np.sign(np.where(np.abs(d) < 1e-9, 0.0, d)))
    return pd.DataFrame({"dir": s.to_numpy(), "res": res, "par": pair}, index=s.index)


def summarize(t: pd.DataFrame) -> dict:
    m = t["res"].notna()
    r = (t["dir"] * t["res"])[m].to_numpy()
    d = t["dir"][m].to_numpy()
    n, w, ties = int((r != 0).sum()), int((r > 0).sum()), int((r == 0).sum())
    lo, _ = wilson(w, n) if n else (float("nan"), 0)
    pnl = np.where(r == 0, 0.0, np.where(r > 0, 0.85, -1.0))
    side = lambda sgn: float((r[d == sgn] > 0).sum() / max((r[d == sgn] != 0).sum(), 1))  # noqa: E731
    return {"operaciones": int(m.sum()), "acierto": w / n if n else None, "lo95": float(lo),
            "acierto_empate_pierde": w / (n + ties) if n + ties else None, "ev": float(pnl.mean()) if len(pnl) else None,
            "p": binom_pvalue_greater(w, n, BE) if n else 1.0, "call": side(1), "put": side(-1)}


def run(out_dir: Path = Path("results/estudio36"), log=print) -> dict:
    feed = DerivFeed()
    der, hd = {v: [] for v in VARIANTS}, []
    for p in PAIRS:
        bars = pd.concat([deriv_month(p, ym, feed) for ym in MONTHS]).sort_index()
        bars = bars[~bars.index.duplicated(keep="last")]
        for v, (n, k, dur) in VARIANTS.items():
            der[v].append(trades(bars, n, k, dur, p))
        hb = pd.concat([seconds(p, ym)[1] for ym in MONTHS]).sort_index()  # velas de precio medio de HistData
        hd.append(trades(hb[~hb.index.duplicated(keep="last")][["o", "h", "l", "c"]], 20, 2.0, 3, p))
        log(f"  {p}: listo")
    res = {v: summarize(pd.concat(der[v])) for v in VARIANTS}
    h = res["H36"]
    crit = {"min_1000": h["operaciones"] >= 1000, "p": h["p"] < 0.05, "wilson": h["lo95"] > BE,
            "simetria": abs(h["call"] - h["put"]) < 0.05}
    d0 = pd.concat(der["H36"]).set_index("par", append=True)
    h0 = pd.concat(hd).set_index("par", append=True)
    common = d0.index.intersection(h0.index)
    same_dir = float((d0.loc[common, "dir"] == h0.loc[common, "dir"]).mean()) if len(common) else None
    both = d0.loc[common, "res"].notna() & h0.loc[common, "res"].notna()
    same_res = float((d0.loc[common][both]["res"] == h0.loc[common][both]["res"]).mean()) if both.any() else None
    dd = pd.concat(der["H36"])
    rep = {"estudio": "Estudio 36 — reversión nocturna con precio de Deriv (pre-registro 767a0b9)", "git_sha": git_sha(),
           "meses": MONTHS, "H36": {**h, "criterios": crit, "pasa": all(crit.values())},
           "informativo": {"fuerte": res["fuerte"], "histdata_L0_mismas_reglas": summarize(pd.concat(hd)),
                           "senales_deriv": int(len(d0)), "senales_histdata": int(len(h0)),
                           "senales_en_comun": int(len(common)), "misma_direccion_en_comun": same_dir,
                           "mismo_resultado_en_comun": same_res,
                           "hora_22": summarize(dd[dd.index.hour == 22])["acierto"]}}
    log(f"H36: pasa={rep['H36']['pasa']} | {h} | {crit}")
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "resultado.json").write_text(json.dumps(jsonable(rep), indent=2, ensure_ascii=False), encoding="utf-8")
    return rep
