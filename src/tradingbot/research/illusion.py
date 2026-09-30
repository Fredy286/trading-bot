"""Demostración: una tasa de acierto alta NO implica rentabilidad.

Entradas al azar con objetivo de ganancia pequeño (1 × σ) y límite de pérdida grande (10 × σ):
se «acierta» casi siempre, pero las pocas pérdidas grandes y los costos dejan el valor esperado
negativo. Con velas M1, si objetivo y límite se tocan en la misma vela se asume la pérdida
(supuesto conservador).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..instruments import Instrument


def asymmetric_exit_demo(bars: pd.DataFrame, inst: Instrument, n_entries: int = 20000, tp_mult: float = 1.0,
                         sl_mult: float = 10.0, max_bars: int = 240, seed: int = 99) -> dict:
    c = bars["c"].to_numpy()
    o = bars["o"].to_numpy()
    hi = bars["h"].to_numpy()
    lo = bars["l"].to_numpy()
    sp = bars["spread_o"].to_numpy()
    lr = np.diff(np.log(c), prepend=np.nan)
    sigma15 = pd.Series(lr).rolling(60, min_periods=50).std().to_numpy() * np.sqrt(15)
    n = len(c)
    cand = np.flatnonzero(~np.isnan(sigma15[: n - max_bars - 1]) & ~np.isnan(o[1: n - max_bars]))
    if len(cand) == 0:
        return {"error": "sin datos suficientes"}
    rng = np.random.default_rng(seed)
    starts = rng.choice(cand, size=min(n_entries, len(cand)), replace=False) + 1  # entrada en apertura t+1
    side = rng.choice([-1.0, 1.0], size=len(starts))
    entry = o[starts]
    dist = sigma15[starts - 1] * entry
    tp = entry + side * tp_mult * dist
    sl = entry - side * sl_mult * dist
    result = np.full(len(starts), np.nan)  # +1 objetivo, −1 límite, NaN sin resolver
    exit_px = np.full(len(starts), np.nan)
    for k in range(max_bars):
        j = starts + k
        hk, lk = hi[j], lo[j]
        pending = np.isnan(result)
        if not pending.any():
            break
        long_ = side > 0
        hit_sl = np.where(long_, lk <= sl, hk >= sl)
        hit_tp = np.where(long_, hk >= tp, lk <= tp)
        gap = np.isnan(hk)
        m_sl = pending & hit_sl & ~gap
        m_tp = pending & hit_tp & ~hit_sl & ~gap
        result[m_sl], exit_px[m_sl] = -1, sl[m_sl]
        result[m_tp], exit_px[m_tp] = 1, tp[m_tp]
    unresolved = np.isnan(result)
    last = starts + max_bars - 1
    exit_px[unresolved] = c[last[unresolved]]
    gross_bps = side * (exit_px - entry) / entry * 1e4
    cost_bps = (sp[starts] + inst.commission_px) / entry * 1e4 + inst.commission_bps
    net = gross_bps - cost_bps
    ok = ~np.isnan(net)
    return {
        "description": "Entradas aleatorias, objetivo 1σ(15m), límite 10σ(15m), máx. 240 min",
        "n": int(ok.sum()),
        "win_rate": float(np.mean(net[ok] > 0)),
        "tp_hit_rate": float(np.mean(result[ok] == 1)),
        "mean_net_bps": float(np.mean(net[ok])),
        "mean_gross_bps": float(np.mean(gross_bps[ok])),
        "mean_cost_bps": float(np.mean(cost_bps[ok])),
        "avg_win_bps": float(np.mean(net[ok][net[ok] > 0])) if np.any(net[ok] > 0) else None,
        "avg_loss_bps": float(np.mean(net[ok][net[ok] <= 0])) if np.any(net[ok] <= 0) else None,
    }
