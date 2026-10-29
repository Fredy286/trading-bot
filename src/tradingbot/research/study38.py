"""Estudio 38 (pre-registro en docs/01, commit 4e674bf): las señales de H20a juzgadas con el precio de BTC del bróker Deriv
(`cryBTCUSD`, velas de 1 min de su API pública). Mismo diseño que el Estudio 37.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from ..live.nocturna import DerivFeed
from .contracts import BinaryContract
from .experiment import git_sha, jsonable
from .study37 import ALPHA, BE, PRED, evaluate

WORK = Path("data/raw/deriv_btc")


def month_candles(ym: str, feed: DerivFeed, work: Path = WORK) -> pd.Series:
    f = Path(work) / f"{ym}.parquet"
    if f.exists():
        return pd.read_parquet(f)["c"]
    start = pd.Timestamp(ym + "-01", tz="UTC")
    end = start + pd.offsets.MonthBegin(1)
    rows, a = [], start
    while a < end:
        b = min(a + pd.Timedelta(minutes=4999), end - pd.Timedelta(minutes=1))
        r = feed._call({"ticks_history": "cryBTCUSD", "style": "candles", "granularity": 60, "count": 5000,
                        "start": int(a.timestamp()), "end": int(b.timestamp())})
        rows.extend(r.get("candles", []))
        a = b + pd.Timedelta(minutes=1)
    df = pd.DataFrame(rows).drop_duplicates("epoch") if rows else pd.DataFrame(columns=["epoch", "close"])
    ser = pd.Series(df["close"].astype(float).to_numpy(), index=pd.to_datetime(df["epoch"], unit="s", utc=True)).sort_index()
    f.parent.mkdir(parents=True, exist_ok=True)
    ser.to_frame("c").to_parquet(f)
    print(f"  Deriv BTC {ym}: {len(ser):,} velas", flush=True)
    return ser


def run(out_dir: Path = Path("results/estudio38"), log=print) -> dict:
    P = pd.read_parquet(PRED)
    side = np.where(P["p"] >= 0.5, 1, -1)
    pdir = np.where(side == 1, P["p"], 1 - P["p"])
    take = (BinaryContract(0.85, "refund").ev(pdir, P["q"].to_numpy()) >= 0.02) & P["y"].notna().to_numpy()
    sig = P[take].assign(side=side[take], pdir=pdir[take])
    feed = DerivFeed()
    months = sorted(set(sig.index.strftime("%Y-%m")))
    dv = pd.concat([month_candles(m, feed) for m in months]).sort_index()
    dv = dv[~dv.index.duplicated(keep="last")]
    c0 = dv.reindex(sig.index).to_numpy()
    c1 = dv.reindex(sig.index + pd.Timedelta(minutes=1)).to_numpy()
    d = c1 - c0
    res = np.where(np.isnan(d), np.nan, np.sign(np.where(np.abs(d) < 0.005, 0.0, d)))
    rep = {"estudio": "Estudio 38 — señales de BTC juzgadas con el precio de Deriv (pre-registro 4e674bf)",
           "git_sha": git_sha(), "cobertura": [str(dv.index.min()), str(dv.index.max())], "hipotesis": {}}
    for h, mask in (("H38a", np.ones(len(sig), bool)), ("H38b", sig["pdir"].to_numpy() >= 0.60)):
        x = evaluate(sig["side"].to_numpy()[mask], res[mask], sig.index[mask])
        crit = {"min_300": x["operaciones"] >= 300, "p": x["p"] < ALPHA, "wilson": x["lo95"] > BE,
                "meses_60": x["meses_ev_positivo"] >= 0.6}
        x.update({"criterios": crit, "pasa": all(crit.values())})
        rep["hipotesis"][h] = x
        log(f"{h}: pasa={x['pasa']} | {x['operaciones']} ops, Deriv {x['acierto']} [{x['lo95']:.4f}] | {crit}")
    yb = sig["y"].to_numpy()
    both = ~np.isnan(res) & (res != 0) & (yb != 0)
    rep["informativo"] = {"resultado_igual_binance_deriv": float((res[both] == yb[both]).mean()) if both.any() else None}
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "resultado.json").write_text(json.dumps(jsonable(rep), indent=2, ensure_ascii=False), encoding="utf-8")
    return rep
