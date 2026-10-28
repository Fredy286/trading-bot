"""Estudio 25 (pre-registro en docs/01, commit a3960ce): reversión nocturna de Bollinger (regla del Estudio 22) en 24
pares que el Estudio 22 no usó, 2025-09-01 → 2026-10-23, todos juntos.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from .experiment import git_sha, jsonable
from .metrics import binom_pvalue_greater, wilson
from .study22 import BE, PAYOUT, color, indicator_rules, lag

PAIRS = ("AUDCAD", "AUDCHF", "AUDJPY", "AUDNZD", "AUDUSD", "CADCHF", "CADJPY", "CHFJPY", "EURAUD", "EURCAD", "EURCHF",
         "EURGBP", "EURJPY", "EURNZD", "GBPAUD", "GBPCAD", "GBPCHF", "GBPJPY", "GBPNZD", "NZDCAD", "NZDCHF", "NZDJPY",
         "NZDUSD", "USDCAD")
START, END = "2025-09-01", "2026-10-24"
RULE = "Bollinger_rev_3min_21a24UTC"


def load_pair(pair: str, root: Path = Path("data/raw/histdata_pares")) -> pd.DataFrame:
    files = [f for f in sorted((Path(root) / pair).glob("*.parquet")) if f.stem >= "2025"]
    df = pd.concat([pd.read_parquet(f) for f in files])[["bid_o", "bid_h", "bid_l", "bid_c"]]
    df.columns = ["o", "h", "l", "c"]
    df = df[~df.index.duplicated(keep="last")].sort_index()
    return df.reindex(pd.date_range(df.index[0], df.index[-1], freq="min", tz="UTC"))


def trades(bars: pd.DataFrame) -> pd.DataFrame:
    """Operaciones de la regla (misma lógica que study22.run_symbol): dirección, resultado a 3 min, una a la vez."""
    d = indicator_rules(bars)[RULE]
    col = color(bars["o"].to_numpy(), bars["c"].to_numpy())
    res = color(bars["o"].to_numpy(), lag(bars["c"].to_numpy(), -2))
    res = np.where(np.isnan(lag(col, -1)) | np.isnan(lag(col, -2)), np.nan, res)
    rows, busy = [], -1
    for i in np.flatnonzero(~np.isnan(d) & ~np.isnan(res)):
        if i > busy:
            rows.append((bars.index[i], d[i], res[i]))
            busy = i + 2
    t = pd.DataFrame(rows, columns=["t", "dir", "res"]).set_index("t")
    return t[(t.index >= pd.Timestamp(START, tz="UTC")) & (t.index < pd.Timestamp(END, tz="UTC"))]


def stats(t: pd.DataFrame) -> dict:
    r = (t["dir"] * t["res"]).to_numpy()
    n, w, ties = int((r != 0).sum()), int((r > 0).sum()), int((r == 0).sum())
    lo, _ = wilson(w, n) if n else (float("nan"), 0)
    pnl = np.where(r == 0, 0.0, np.where(r > 0, PAYOUT, -1.0))
    return {"operaciones": int(len(t)), "sin_empate": n, "acierto": w / n if n else None, "lo95": float(lo),
            "acierto_empate_pierde": w / (n + ties) if n + ties else None, "ev": float(pnl.mean()) if len(t) else None,
            "p": binom_pvalue_greater(w, n, BE) if n else 1.0, "p_azar": binom_pvalue_greater(w, n, 0.5) if n else 1.0}


def run(out_dir: Path = Path("results/estudio25"), log=print) -> dict:
    parts = []
    for p in PAIRS:
        t = trades(load_pair(p)).assign(par=p)
        parts.append(t)
        log(f"  {p}: {len(t)} operaciones")
    allt = pd.concat(parts).sort_index()
    main = stats(allt)
    r = allt["dir"] * allt["res"]
    pnl = np.where(r == 0, 0.0, np.where(r > 0, PAYOUT, -1.0))
    mens = pd.Series(pnl, index=allt.index).groupby(allt.index.strftime("%Y-%m")).mean()
    main["meses_ev_positivo"] = float((mens > 0).mean())
    crit = {"min_1000": main["operaciones"] >= 1000, "p": main["p"] < 0.05, "wilson": main["lo95"] > BE,
            "meses_60": main["meses_ev_positivo"] >= 0.6}
    rep = {"estudio": "Estudio 25 — reversión nocturna en 24 pares nuevos (pre-registro a3960ce)", "git_sha": git_sha(),
           "periodo": [START, END], **main, "mensual": mens.round(4).to_dict(), "criterios": crit,
           "pasa": all(crit.values()),
           "por_par": {p: stats(g) for p, g in allt.groupby("par")},
           "por_hora": {int(h): stats(g)["acierto"] for h, g in allt.groupby(allt.index.hour)}}
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "resultado.json").write_text(json.dumps(jsonable(rep), indent=2, ensure_ascii=False), encoding="utf-8")
    log(f"H25: pasa={rep['pasa']} | {crit} | {main}")
    return rep
