"""Estudio 37 (pre-registro en docs/01, commit fb4d991): las señales de H20a (modelo de BTC con datos de Binance) juzgadas
con el precio de Coinbase (BTC-USD): resultado = signo(cierre de la vela t + 1 − cierre de la vela t).
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
import requests

from .contracts import BinaryContract
from .experiment import git_sha, jsonable
from .metrics import binom_pvalue_greater, wilson

URL = "https://api.exchange.coinbase.com/products/BTC-USD/candles"
WORK = Path("data/raw/coinbase_btcusd")
PRED = Path("results/estudio20/predicciones.parquet")
ALPHA = 0.025
BE = 1 / 1.85


def month_candles(ym: str, work: Path = WORK, session=None) -> pd.Series:
    """Cierres de las velas de 1 min de Coinbase del mes `ym` (300 velas por petición), con caché."""
    f = Path(work) / f"{ym}.parquet"
    if f.exists():
        return pd.read_parquet(f)["c"]
    s = session or requests.Session()
    start = pd.Timestamp(ym + "-01", tz="UTC")
    end = start + pd.offsets.MonthBegin(1)
    rows = []
    a = start
    while a < end:
        b = min(a + pd.Timedelta(minutes=299), end - pd.Timedelta(minutes=1))
        for intento in range(5):
            r = s.get(URL, params={"granularity": 60, "start": a.strftime("%Y-%m-%dT%H:%M:%SZ"),
                                   "end": b.strftime("%Y-%m-%dT%H:%M:%SZ")}, timeout=30)
            if r.status_code == 200:
                rows.extend(r.json())
                break
            time.sleep(2 * (intento + 1))  # límite de velocidad u otro fallo temporal
        a = b + pd.Timedelta(minutes=1)
        time.sleep(0.15)
    df = pd.DataFrame(rows, columns=["t", "l", "h", "o", "c", "v"]).drop_duplicates("t")
    ser = pd.Series(df["c"].astype(float).to_numpy(), index=pd.to_datetime(df["t"], unit="s", utc=True)).sort_index()
    f.parent.mkdir(parents=True, exist_ok=True)
    ser.to_frame("c").to_parquet(f)
    print(f"  Coinbase {ym}: {len(ser):,} velas", flush=True)
    return ser


def evaluate(side, res, times, n_boot=None) -> dict:
    r = side * res
    m = ~np.isnan(r)
    r, tt = r[m], times[m]
    n, w = int((r != 0).sum()), int((r > 0).sum())
    lo, _ = wilson(w, n) if n else (float("nan"), 0)
    pnl = np.where(r == 0, 0.0, np.where(r > 0, 0.85, -1.0))
    mens = pd.Series(pnl, index=tt).groupby(tt.strftime("%Y-%m")).mean()
    return {"operaciones": int(m.sum()), "acierto": w / n if n else None, "lo95": float(lo),
            "p": binom_pvalue_greater(w, n, BE) if n else 1.0, "ev": float(pnl.mean()) if len(pnl) else None,
            "meses_ev_positivo": float((mens > 0).mean()) if len(mens) else 0.0,
            "mensual": {k: round(float(v), 4) for k, v in mens.items()}}


def run(out_dir: Path = Path("results/estudio37"), log=print) -> dict:
    P = pd.read_parquet(PRED)
    side = np.where(P["p"] >= 0.5, 1, -1)
    pdir = np.where(side == 1, P["p"], 1 - P["p"])
    take = BinaryContract(0.85, "refund").ev(pdir, P["q"].to_numpy()) >= 0.02  # política de H20a
    take &= P["y"].notna().to_numpy()
    sig = P[take].assign(side=side[take], pdir=pdir[take])
    months = sorted(set(sig.index.strftime("%Y-%m")))
    s = requests.Session()
    cb = pd.concat([month_candles(m, session=s) for m in months]).sort_index()
    cb = cb[~cb.index.duplicated(keep="last")]
    c0 = cb.reindex(sig.index).to_numpy()
    c1 = cb.reindex(sig.index + pd.Timedelta(minutes=1)).to_numpy()
    d = c1 - c0
    res_cb = np.where(np.isnan(d), np.nan, np.sign(np.where(np.abs(d) < 0.005, 0.0, d)))
    rep = {"estudio": "Estudio 37 — señales de BTC juzgadas con Coinbase (pre-registro fb4d991)", "git_sha": git_sha(),
           "hipotesis": {}}
    for h, mask in (("H37a", np.ones(len(sig), bool)), ("H37b", sig["pdir"].to_numpy() >= 0.60)):
        x = evaluate(sig["side"].to_numpy()[mask], res_cb[mask], sig.index[mask])
        crit = {"min_300": x["operaciones"] >= 300, "p": x["p"] < ALPHA, "wilson": x["lo95"] > BE,
                "meses_60": x["meses_ev_positivo"] >= 0.6}
        x.update({"criterios": crit, "pasa": all(crit.values()),
                  "binance_mismas_senales": evaluate(sig["side"].to_numpy()[mask], sig["y"].to_numpy()[mask],
                                                     sig.index[mask])["acierto"]})
        rep["hipotesis"][h] = x
        log(f"{h}: pasa={x['pasa']} | {x['operaciones']} ops, Coinbase {x['acierto']:.4f} [{x['lo95']:.4f}] "
            f"(Binance {x['binance_mismas_senales']:.4f}) | {crit}")
    yb = sig["y"].to_numpy()
    both = ~np.isnan(res_cb) & (res_cb != 0) & (yb != 0)
    agree = res_cb[both] == yb[both]
    win_b = (sig["side"].to_numpy()[both] * yb[both]) > 0
    rep["informativo"] = {"resultado_igual_binance_coinbase": float(agree.mean()),
                          "acierto_binance_cuando_no_coinciden": float(win_b[~agree].mean()) if (~agree).any() else None}
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "resultado.json").write_text(json.dumps(jsonable(rep), indent=2, ensure_ascii=False), encoding="utf-8")
    return rep
