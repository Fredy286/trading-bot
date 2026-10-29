"""Estudio 30 (pre-registro en docs/01, commit 297b9c1): la reversión de Bollinger (regla de H27b/H28a) en cada hora UTC
de 0 a 20 (divisas, Parte A) y de noche en oro, S&P 500 y BTC (Parte B), 2025-11 → 2026-09.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from .experiment import git_sha, jsonable
from .study22 import BE
from .study25 import PAIRS
from .study27 import price_at, seconds, stats
from .study28 import band_signal, one_at_a_time
from .study22 import holm

MONTHS = ("2025-11", "2025-12", "2026-01", "2026-02", "2026-03", "2026-04", "2026-05", "2026-06", "2026-07",
          "2026-08", "2026-09")
L, DUR = 10, 180
OTHER = ("XAUUSD", "SPXUSD", "BTCUSDT")


def histdata(pair: str) -> tuple[pd.Series, pd.DataFrame]:
    parts = [seconds(pair, ym) for ym in MONTHS]
    sec = pd.concat([p[0] for p in parts])["mid"].sort_index()
    bars = pd.concat([p[1] for p in parts]).sort_index()
    return sec[~sec.index.duplicated(keep="last")], bars[~bars.index.duplicated(keep="last")]


def binance_btc(root: Path = Path("data/processed/senal/seg")) -> tuple[pd.Series, pd.DataFrame]:
    """Cierres de las velas de 1 s (último negociado) y velas de 1 min construidas con ellos."""
    sec = pd.concat([pd.read_parquet(Path(root) / f"{ym}.parquet", columns=["c"]) for ym in MONTHS])["c"].sort_index()
    sec = sec[~sec.index.duplicated(keep="last")]
    g = sec.resample("min")
    return sec, pd.DataFrame({"o": g.first(), "h": g.max(), "l": g.min(), "c": g.last()})


def trades(sec: pd.Series, bars: pd.DataFrame, name: str, hours) -> pd.DataFrame:
    bars = bars.reindex(pd.date_range(bars.index[0], bars.index[-1], freq="min", tz="UTC"))
    sig = band_signal(bars)
    sig = sig[sig.index >= pd.Timestamp(MONTHS[0] + "-01", tz="UTC")]
    out = []
    for h in hours:
        s = sig[np.isin(sig.index.hour, h if isinstance(h, tuple) else (h,))]
        s = s[one_at_a_time(s.index)]
        e = price_at(sec, s.index + pd.Timedelta(seconds=L))
        x = price_at(sec, s.index + pd.Timedelta(seconds=L + DUR))
        d = x - e
        res = np.where(np.isnan(d), np.nan, np.sign(np.where(np.abs(d) < 1e-9, 0.0, d)))
        out.append(pd.DataFrame({"grupo": str(h), "dir": s.to_numpy(), "res": res, "par": name}, index=s.index))
    return pd.concat(out)


def run(out_dir: Path = Path("results/estudio30"), log=print) -> dict:
    rows = []
    for p in PAIRS:
        sec, bars = histdata(p)
        rows.append(trades(sec, bars, p, list(range(21))))
        log(f"  {p}: listo")
    fx = pd.concat(rows)
    other = []
    for m in OTHER:
        sec, bars = binance_btc() if m == "BTCUSDT" else histdata(m)
        other.append(trades(sec, bars, m, [(21, 22, 23)]))
        log(f"  {m}: listo")
    oth = pd.concat(other)
    hyps = {f"A_{h:02d}UTC": fx[fx["grupo"] == str(h)] for h in range(21)}
    hyps.update({f"B_{m}": oth[oth["par"] == m] for m in OTHER})
    res = {}
    for k, g in hyps.items():
        res[k] = stats(g["dir"].to_numpy(), g["res"].to_numpy(), g.index)
    adj = holm([res[k]["p"] for k in res])
    for (k, x), pa in zip(res.items(), adj):
        min_n = 1000 if k.startswith("A_") else 500
        crit = {"min_n": x["operaciones"] >= min_n, "holm": pa < 0.05, "wilson": x["lo95"] > BE,
                "meses_8de11": x["meses_ev_positivo"] >= 8, "simetria": abs(x["call"] - x["put"]) < 0.05}
        x.update({"p_holm": pa, "criterios": crit, "pasa": all(crit.values())})
        log(f"{k}: pasa={x['pasa']} | {x['operaciones']} ops, acierto {x['acierto']:.4f} [{x['lo95']:.4f}] "
            f"CALL {x['call']:.3f} PUT {x['put']:.3f} meses+ {x['meses_ev_positivo']}")
    rep = {"estudio": "Estudio 30 — reversión de Bollinger en otras horas y mercados (pre-registro 297b9c1)",
           "git_sha": git_sha(), "meses": MONTHS, "hipotesis": res, "pasan": [k for k in res if res[k]["pasa"]]}
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "resultado.json").write_text(json.dumps(jsonable(rep), indent=2, ensure_ascii=False), encoding="utf-8")
    return rep
