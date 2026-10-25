"""Estudio 11 (pre-registro en docs/01, commit 3a7da57): «regla de la primera vela» de redes. Rango de 9:30–9:35
(hora de Nueva York), ruptura en 1 min que deja un FVG, retesteo del FVG con vela envolvente, 3:1, una operación
por día. Nasdaq 100, S&P 500 y oro (HistData), fase A 2022-01 → 2025-08 y fase B 2025-09 → 2026-08.
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
from .metrics import block_bootstrap_mean

COST = {"NSXUSD": 1.0, "SPXUSD": 0.5, "XAUUSD": 0.25 + 0.07}  # ida y vuelta, unidades de precio
HYPS = {"H11-NQ": "NSXUSD", "H11-SPX": "SPXUSD", "H11-XAU": "XAUUSD"}
ALPHA = 0.05 / 3
PHASES = {"A": ("2022-01-01", "2025-09-01"), "B": ("2025-09-01", "2026-09-01")}
OPEN, OR_END, FIRST_K, LAST_ENTRY, CLOSE = 570, 575, 577, 660, 960  # minutos del día, hora de Nueva York
RR = 3.0


def day_trade(o, h, l, c, m, cost: float) -> dict | None:
    """Una sesión (arrays de velas de 1 min en orden y su minuto del día en Nueva York). None si no hay rango."""
    orm = (m >= OPEN) & (m < OR_END)
    if orm.sum() != 5 or np.isnan(h[orm]).any() or np.isnan(l[orm]).any():
        return None
    orh, orl = np.nanmax(h[orm]), np.nanmin(l[orm])
    idx = np.flatnonzero((m >= OPEN) & (m < CLOSE))
    pending = []  # (lado, k, borde_cancelación, borde_retesteo)
    for pos, i in enumerate(idx):
        if np.isnan(c[i]):
            continue
        # 1) ¿La vela i es la entrada de algún FVG pendiente? (retesteo + envolvente)
        if m[i] < LAST_ENTRY and pos >= 1 and not np.isnan(c[i - 1]):
            for sd, k, cancel_px, touch_px in pending:
                if sd == 1:
                    ok = (l[i] <= touch_px and c[i - 1] < o[i - 1] and c[i] > o[i]
                          and o[i] <= c[i - 1] and c[i] >= o[i - 1])
                    sl = min(l[i], cancel_px)
                else:
                    ok = (h[i] >= touch_px and c[i - 1] > o[i - 1] and c[i] < o[i]
                          and o[i] >= c[i - 1] and c[i] <= o[i - 1])
                    sl = max(h[i], cancel_px)
                if ok:
                    return _manage(o, h, l, c, m, idx[pos + 1:], sd, c[i], sl, cost, i, k)
        # 2) Cancelaciones por cierre al otro lado del FVG.
        pending = [p for p in pending if not ((p[0] == 1 and c[i] < p[2]) or (p[0] == -1 and c[i] > p[2]))]
        # 3) ¿La vela i (como k) cierra un FVG de ruptura?
        if FIRST_K <= m[i] < LAST_ENTRY and pos >= 2:
            a, b = idx[pos - 2], idx[pos - 1]
            if not (np.isnan(h[a]) or np.isnan(c[b])):
                if h[a] < l[i] and c[b] > orh:
                    pending.append((1, i, h[a], l[i]))
                elif l[a] > h[i] and c[b] < orl:
                    pending.append((-1, i, l[a], h[i]))
    return {"sin_entrada": True}


def _manage(o, h, l, c, m, rest, sd, entry, sl, cost, j, k) -> dict:
    risk = abs(entry - sl)
    if risk <= cost:
        return {"riesgo_menor_que_costo": True}
    tp = entry + sd * RR * risk
    exit_px, why = None, "16:00"
    last = None
    for i in rest:
        if np.isnan(c[i]):
            continue
        last = i
        if (sd == 1 and l[i] <= sl) or (sd == -1 and h[i] >= sl):
            exit_px, why = sl, "SL"
            break
        if (sd == 1 and h[i] >= tp) or (sd == -1 and l[i] <= tp):
            exit_px, why = tp, "TP"
            break
    if exit_px is None:
        exit_px = c[last] if last is not None else entry
    return {"lado": sd, "entrada": float(entry), "sl": float(sl), "salida": float(exit_px), "motivo": why,
            "R": float(((exit_px - entry) * sd - cost) / risk), "k": int(k), "j": int(j)}


def simple_orb(o, c, m, cost: float) -> float | None:
    """ORB de Zarattini y Aziz (informativo): dirección de la primera vela de 5 min, de 9:35 a 16:00."""
    first = np.flatnonzero((m >= OPEN) & (m < OR_END))
    rest = np.flatnonzero((m >= OR_END) & (m < CLOSE) & ~np.isnan(c))
    if len(first) != 5 or not len(rest) or np.isnan(o[first[0]]) or np.isnan(c[first[-1]]):
        return None
    sd = np.sign(c[first[-1]] - o[first[0]])
    if sd == 0 or np.isnan(o[rest[0]]):
        return None
    return float((c[rest[-1]] - o[rest[0]]) * sd - cost) / o[rest[0]] * 1e4  # puntos básicos netos


def run_symbol(bars: pd.DataFrame, cost: float) -> tuple[pd.DataFrame, dict, list]:
    ny = bars.index.tz_convert("America/New_York")
    m_all = (ny.hour * 60 + ny.minute).to_numpy()
    o, h, l, c = (bars[k].to_numpy() for k in ("o", "h", "l", "c"))
    days = pd.Index(ny.date)
    rows, counts, orb = [], {"dias": 0, "sin_rango": 0, "sin_entrada": 0, "riesgo_menor_que_costo": 0}, []
    starts = np.flatnonzero(np.r_[True, days[1:] != days[:-1]])
    ends = np.r_[starts[1:], len(days)]
    for s, e in zip(starts, ends):
        if days[s].weekday() >= 5:
            continue
        counts["dias"] += 1
        sl = slice(s, e)
        r = day_trade(o[sl], h[sl], l[sl], c[sl], m_all[sl], cost)
        b = simple_orb(o[sl], c[sl], m_all[sl], cost)
        if b is not None:
            orb.append(b)
        if r is None:
            counts["sin_rango"] += 1
        elif "lado" not in r:
            counts["sin_entrada" if r.get("sin_entrada") else "riesgo_menor_que_costo"] += 1
        else:
            rows.append({"time": bars.index[s + r["j"]], **{k: r[k] for k in ("lado", "entrada", "sl", "salida",
                                                                              "motivo", "R")}})
    return pd.DataFrame(rows), counts, orb


def evaluate(tr: pd.DataFrame, n_boot: int = 2000) -> dict:
    if len(tr) == 0:
        return {"operaciones": 0, "pasa": False}
    t = pd.DatetimeIndex(tr["time"])
    b = block_bootstrap_mean(tr["R"].to_numpy(), t.strftime("%G-%V"), n_boot=n_boot, level=1 - ALPHA)
    q = pd.Series(tr["R"].to_numpy()).groupby(pd.PeriodIndex(t.tz_convert(None), freq="Q")).sum()
    pos_q = float((q > 0).mean())
    crit = {"min_200": len(tr) >= 200, "ic_R_positivo": b["lo"] > 0, "trimestres_60": pos_q >= 0.6}
    return {"operaciones": int(len(tr)), "winrate_tp": float((tr["motivo"] == "TP").mean()),
            "salidas": tr["motivo"].value_counts().to_dict(), "R_neto_medio": b["mean"], "ic98_33": [b["lo"], b["hi"]],
            "trimestres_positivos": pos_q, "criterios": crit, "pasa": all(crit.values())}


def run(root: Path = Path("data/raw"), out_dir: Path = Path("results/estudio11"), n_boot: int = 2000) -> dict:
    report = {"estudio": "Estudio 11 — regla de la primera vela (pre-registro 3a7da57)", "git_sha": git_sha(),
              "costos": COST, "fases": {}}
    passing = list(HYPS)
    for phase, (a, b) in PHASES.items():
        res = {}
        for hname in passing:
            sym = HYPS[hname]
            raw = store.load(root, get_instrument(sym), source="histdata")
            bars, _ = to_canonical(raw, fill_gaps=True)
            bars = bars[(bars.index >= pd.Timestamp(a, tz="UTC")) & (bars.index < pd.Timestamp(b, tz="UTC"))]
            if not len(bars):
                res[hname] = {"nota": "sin datos"}
                continue
            tr, counts, orb = run_symbol(bars, COST[sym])
            res[hname] = {**evaluate(tr, n_boot), "conteo_dias": counts,
                          "orb_simple_informativo": {"dias": len(orb), "neto_medio_pb": float(np.mean(orb)) if orb else None,
                                                     "dias_positivos": float(np.mean(np.array(orb) > 0)) if orb else None}}
        report["fases"][phase] = {"periodo": [a, b], "resultados": res}
        passing = [h for h in passing if res.get(h, {}).get("pasa")]
        if not passing:
            break
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "resultado.json").write_text(json.dumps(jsonable(report), indent=2, ensure_ascii=False),
                                            encoding="utf-8")
    return report
