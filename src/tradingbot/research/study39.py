"""Estudio 39 (pre-registro en docs/01, commit b452ff0): reversión nocturna con el precio de Deriv, solo entradas de 22:00
a 23:59 UTC (Deriv no deja operar divisas de 20:50 a 22:00) y vencimiento de 15 min (su mínimo), 19 pares, 2026-04 → 09.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from ..live.nocturna import PAIRS
from .experiment import git_sha, jsonable
from .study22 import BE
from .study34 import band, one_at_a_time
from .study36 import MONTHS, WORK, summarize

DUR = 15
HYPS = {"H39a": (20, 2.0), "H39b": (30, 2.5)}
ALPHA = 0.025


def trades(bars: pd.DataFrame, n: int, k: float, pair: str) -> pd.DataFrame:
    bars = bars.reindex(pd.date_range(bars.index[0], bars.index[-1], freq="min", tz="UTC"))
    s = band(bars, n, k)
    s = s[(s.index >= pd.Timestamp(MONTHS[0] + "-01", tz="UTC")) & (s.index.hour >= 22)]
    s = s[one_at_a_time(s.index, DUR)]
    o = bars["o"].reindex(s.index).to_numpy()
    c = bars["c"].reindex(s.index + pd.Timedelta(minutes=DUR - 1)).to_numpy()
    d = c - o
    res = np.where(np.isnan(d), np.nan, np.sign(np.where(np.abs(d) < 1e-9, 0.0, d)))
    return pd.DataFrame({"dir": s.to_numpy(), "res": res, "par": pair}, index=s.index)


def run(out_dir: Path = Path("results/estudio39"), log=print) -> dict:
    rows = {h: [] for h in HYPS}
    for p in PAIRS:
        bars = pd.concat([pd.read_parquet(Path(WORK) / p / f"{ym}.parquet") for ym in MONTHS]).sort_index()
        bars = bars[~bars.index.duplicated(keep="last")]
        for h, (n, k) in HYPS.items():
            rows[h].append(trades(bars, n, k, p))
    rep = {"estudio": "Estudio 39 — reversión nocturna operable en Deriv (pre-registro b452ff0)", "git_sha": git_sha(),
           "hipotesis": {}}
    for h in HYPS:
        t = pd.concat(rows[h])
        x = summarize(t)
        crit = {"min_500": x["operaciones"] >= 500, "p": x["p"] < ALPHA, "wilson": x["lo95"] > BE,
                "simetria": abs(x["call"] - x["put"]) < 0.05}
        x.update({"criterios": crit, "pasa": all(crit.values()),
                  "por_hora": {int(hh): summarize(g)["acierto"] for hh, g in t.groupby(t.index.hour)}})
        rep["hipotesis"][h] = x
        log(f"{h}: pasa={x['pasa']} | {x['operaciones']} ops, acierto {x['acierto']:.4f} [{x['lo95']:.4f}] "
            f"CALL {x['call']:.3f} PUT {x['put']:.3f} | {crit} | por hora {x['por_hora']}")
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "resultado.json").write_text(json.dumps(jsonable(rep), indent=2, ensure_ascii=False), encoding="utf-8")
    return rep
