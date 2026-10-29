"""Estudio 31 (pre-registro en docs/01, commit ab7e9ff; SOLO INFORMATIVO): solidez de la reversión nocturna frente a
los parámetros de la banda (N, K) y el vencimiento, 21–24 UTC, 24 pares, precio medio, clic a +10 s, 2025-11 → 2026-09.
"""

from __future__ import annotations

import json
from itertools import product
from pathlib import Path

import numpy as np
import pandas as pd

from .experiment import git_sha, jsonable
from .study22 import BE, _sma
from .study25 import PAIRS
from .study27 import price_at, stats
from .study30 import MONTHS, histdata

NS, KS, EXPS, L = (14, 20, 30), (1.5, 2.0, 2.5), (1, 2, 3, 5), 10
BASE = (20, 2.0, 3)


def signal(bars: pd.DataFrame, n: int, k: float) -> pd.Series:
    real = bars.dropna()
    c = real["c"].to_numpy()
    mid, sd = _sma(c, n), pd.Series(c).rolling(n).std(ddof=0).to_numpy()
    bb = np.where(c > mid + k * sd, -1.0, np.where(c < mid - k * sd, 1.0, np.nan))
    s = pd.Series(bb, index=real.index + pd.Timedelta(minutes=1)).dropna()
    return s[(s.index.hour >= 21) & (s.index >= pd.Timestamp(MONTHS[0] + "-01", tz="UTC"))]


def one_at_a_time(t: pd.DatetimeIndex, minutes: int) -> np.ndarray:
    keep, busy = np.zeros(len(t), bool), None
    for i, x in enumerate(t):
        if busy is None or x >= busy:
            keep[i], busy = True, x + pd.Timedelta(minutes=minutes)
    return keep


def run(out_dir: Path = Path("results/estudio31"), log=print) -> dict:
    rows = {c: [] for c in product(NS, KS, EXPS)}
    for p in PAIRS:
        sec, bars = histdata(p)
        bars = bars.reindex(pd.date_range(bars.index[0], bars.index[-1], freq="min", tz="UTC"))
        for n, k in product(NS, KS):
            s = signal(bars, n, k)
            for e in EXPS:
                ss = s[one_at_a_time(s.index, e)]
                a = price_at(sec, ss.index + pd.Timedelta(seconds=L))
                b = price_at(sec, ss.index + pd.Timedelta(seconds=L + 60 * e))
                d = b - a
                res = np.where(np.isnan(d), np.nan, np.sign(np.where(np.abs(d) < 1e-9, 0.0, d)))
                rows[(n, k, e)].append(pd.DataFrame({"dir": ss.to_numpy(), "res": res}, index=ss.index))
        log(f"  {p}: listo")
    grid = {}
    for c, parts in rows.items():
        g = pd.concat(parts)
        x = stats(g["dir"].to_numpy(), g["res"].to_numpy(), g.index)
        x.pop("mensual")
        grid[f"N{c[0]}_K{c[1]}_{c[2]}min"] = x
    neigh = [(14, 2.0, 3), (30, 2.0, 3), (20, 1.5, 3), (20, 2.5, 3), (20, 2.0, 2), (20, 2.0, 5)]
    key = lambda c: f"N{c[0]}_K{c[1]}_{c[2]}min"  # noqa: E731
    vec = {key(c): grid[key(c)] for c in neigh}
    solid = all(v["acierto"] > BE and v["lo95"] > 0.52 for v in vec.values())
    rep = {"estudio": "Estudio 31 — solidez de parámetros (informativo, pre-registro ab7e9ff)", "git_sha": git_sha(),
           "base": grid[key(BASE)], "vecinas": {k: v["acierto"] for k, v in vec.items()}, "solida": solid,
           "rejilla": grid}
    for k, v in grid.items():
        log(f"{k}: {v['operaciones']} ops, acierto {v['acierto']:.4f}")
    log(f"Sólida: {solid} | vecinas {rep['vecinas']}")
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "resultado.json").write_text(json.dumps(jsonable(rep), indent=2, ensure_ascii=False), encoding="utf-8")
    return rep
