"""Estudio 8 (pre-registro en docs/01, commit dffe312): el indicador «Golden BIAS 200» reconstruido en XAU/USD.

Reglas fijas (no se entrenan): SMA15/SMA200 con distancia mínima de 1·ATR14, vela a favor, sesiones en hora
de México y, en dos variantes, coincidencia multitemporal (5/15/60/240 min). Se prueba como contado (orden
límite en el retroceso desde la SMA15, SL/TP de 1,5·ATR, 60 velas máximo) y como binaria a 5 min con entrada
1 min después. Fase A 2022-01 → 2025-08; fase B 2025-09 → 2026-08 solo para las que pasen A.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from ..data import store
from ..data.clean import to_canonical
from ..instruments import get_instrument
from .contracts import BinaryContract
from .experiment import git_sha, jsonable
from .labels import make_labels
from .metrics import binom_pvalue_greater, block_bootstrap_mean, wilson

COST = 0.25 + 0.07  # spread supuesto + comisión, USD/oz ida y vuelta (escenario optimista del proyecto)
MIN_DIST, OFFSET, SL_ATR, TP_ATR = 1.0, 0.25, 1.5, 1.5
FILL_BARS, MAX_HOLD = 10, 60
SESSIONS_MX = ((8 * 60, 12 * 60), (17 * 60 + 30, 23 * 60), (60, 7 * 60))  # minutos del día, hora de México
MTF = (5, 15, 60, 240)
ALPHA = 0.0125  # Bonferroni, 4 hipótesis
PHASES = {"A": ("2022-01-01", "2025-09-01"), "B": ("2025-09-01", "2026-09-01")}
HYPS = {"H8a": ("contado", False), "H8b": ("contado", True), "H8c": ("binaria", False), "H8d": ("binaria", True)}


def indicators(bars: pd.DataFrame) -> pd.DataFrame:
    c, h, l = bars["c"], bars["h"], bars["l"]
    prev = c.shift(1)
    tr = pd.concat([h - l, (h - prev).abs(), (l - prev).abs()], axis=1).max(axis=1, skipna=False)
    return pd.DataFrame({"sma15": c.rolling(15, min_periods=15).mean(),
                         "sma200": c.rolling(200, min_periods=200).mean(),
                         "atr": tr.rolling(14, min_periods=14).mean()}, index=bars.index)


def in_session(index: pd.DatetimeIndex) -> np.ndarray:
    """El CIERRE de la vela (apertura + 1 min) cae en una sesión, en hora de Ciudad de México."""
    close = (index + pd.Timedelta(minutes=1)).tz_convert("America/Mexico_City")
    m = (close.hour * 60 + close.minute).to_numpy()
    return np.any([(m >= a) & (m < b) for a, b in SESSIONS_MX], axis=0)


def mtf_arrows(bars: pd.DataFrame, tf: int) -> np.ndarray:
    """+1/−1: la última vela de `tf` minutos CERRADA al cierre de t está por encima/debajo de su SMA20."""
    c = bars["c"]
    tfc = c.resample(f"{tf}min", label="left", closed="left").last().dropna()
    arrow = np.sign(tfc - tfc.rolling(20, min_periods=20).mean())
    arrow.index = arrow.index + pd.Timedelta(minutes=tf)  # momento en que esa vela ya está cerrada
    close_t = bars.index + pd.Timedelta(minutes=1)
    pos = np.searchsorted(arrow.index.asi8, close_t.asi8, side="right") - 1
    vals = arrow.to_numpy()
    return np.where(pos >= 0, vals[np.clip(pos, 0, None)], np.nan)


def signals(bars: pd.DataFrame, ind: pd.DataFrame, mtf: bool) -> np.ndarray:
    c, o = bars["c"].to_numpy(), bars["o"].to_numpy()
    s15, s200, atr = ind["sma15"].to_numpy(), ind["sma200"].to_numpy(), ind["atr"].to_numpy()
    with np.errstate(invalid="ignore"):
        long = (c > s15) & (c > s200) & (s15 > s200) & (s15 - s200 >= MIN_DIST * atr) & (c > o)
        short = (c < s15) & (c < s200) & (s15 < s200) & (s200 - s15 >= MIN_DIST * atr) & (c < o)
    side = np.where(long, 1, np.where(short, -1, 0))
    side[~in_session(bars.index)] = 0
    if mtf:
        arrows = np.column_stack([mtf_arrows(bars, tf) for tf in MTF])
        agree = np.all(arrows == side[:, None], axis=1)
        side[~agree] = 0
    return side


def simulate_spot(bars: pd.DataFrame, ind: pd.DataFrame, side: np.ndarray) -> pd.DataFrame:
    """Una operación a la vez: orden límite en el retroceso, SL/TP de 1,5·ATR, 60 velas máximo."""
    o, h, l = (bars[k].to_numpy() for k in ("o", "h", "l"))
    c = bars["c"].ffill().to_numpy()  # salida por tiempo en un minuto sin datos: último cierre conocido
    s15, atr = ind["sma15"].to_numpy(), ind["atr"].to_numpy()
    n, t, rows = len(bars), 0, []
    cand = np.flatnonzero(side != 0)
    i = 0
    while i < len(cand):
        t = cand[i]
        sd = int(side[t])
        a = atr[t]
        lim = s15[t] + sd * OFFSET * a
        k = fill = None
        if (sd == 1 and lim >= c[t]) or (sd == -1 and lim <= c[t]):
            if t + 1 < n and not np.isnan(o[t + 1]):
                k, fill = t + 1, o[t + 1]  # el retroceso ya se cumplió: a mercado
        else:
            for j in range(t + 1, min(t + 1 + FILL_BARS, n)):
                if np.isnan(l[j]):
                    continue
                if sd == 1 and l[j] <= lim:
                    k, fill = j, min(lim, o[j])
                    break
                if sd == -1 and h[j] >= lim:
                    k, fill = j, max(lim, o[j])
                    break
        if k is None:
            busy = t + FILL_BARS  # orden pendiente sin llenar
            rows.append({"t": t, "lado": sd, "llenada": False})
        else:
            sl, tp = fill - sd * SL_ATR * a, fill + sd * TP_ATR * a
            exit_px = why = None
            last = min(k + MAX_HOLD, n - 1)
            for j in range(k, last + 1):
                if np.isnan(l[j]):
                    continue
                hit_sl = (l[j] <= sl) if sd == 1 else (h[j] >= sl)
                hit_tp = (h[j] >= tp) if sd == 1 else (l[j] <= tp)
                if hit_sl:  # en la vela de entrada y si caen ambos en la misma vela, cuenta el SL
                    exit_px, why, busy = sl, "SL", j
                    break
                if hit_tp and j > k:
                    exit_px, why, busy = tp, "TP", j
                    break
            if exit_px is None:
                exit_px, why, busy = c[last], "tiempo", last
            gross = (exit_px - fill) * sd
            rows.append({"t": t, "lado": sd, "llenada": True, "entrada": fill, "salida": exit_px, "motivo": why,
                         "neto": gross - COST, "R": gross / (SL_ATR * a)})
        while i < len(cand) and cand[i] <= busy:
            i += 1
    out = pd.DataFrame(rows)
    if len(out):
        out["time"] = bars.index[out["t"].to_numpy()]
    return out


def simulate_binary(bars: pd.DataFrame, side: np.ndarray, point: float) -> pd.DataFrame:
    """Entrada en la apertura de t+2 (1 min después), vencimiento 5 min; sin solapamiento."""
    lab = make_labels(bars, 5, 2, point)
    d = lab["dir"].to_numpy()
    rows, busy = [], -1
    for t in np.flatnonzero(side != 0):
        if t <= busy or np.isnan(d[t]):
            continue
        busy = t + 6  # vence al cierre de t+6
        res = int(d[t] * side[t])
        rows.append({"t": t, "lado": int(side[t]), "resultado": res,
                     "pnl": 0.0 if res == 0 else (0.85 if res > 0 else -1.0)})
    out = pd.DataFrame(rows)
    if len(out):
        out["time"] = bars.index[out["t"].to_numpy()]
    return out


def _quarter_share(times: pd.Series, pnl: np.ndarray) -> float:
    q = pd.PeriodIndex(pd.DatetimeIndex(times).tz_convert(None), freq="Q")
    by = pd.Series(pnl).groupby(q).sum()
    return float((by > 0).mean()) if len(by) else 0.0


def evaluate_spot(tr: pd.DataFrame, n_boot: int = 2000) -> dict:
    f = tr[tr["llenada"]] if len(tr) else tr
    if not len(f):
        return {"senales": int(len(tr)), "operaciones": 0, "pasa": False}
    day = pd.DatetimeIndex(f["time"]).strftime("%Y-%m-%d")
    b = block_bootstrap_mean(f["neto"].to_numpy(), day, n_boot=n_boot, level=1 - ALPHA)
    pos_q = _quarter_share(f["time"], f["neto"].to_numpy())
    crit = {"min_300": len(f) >= 300, "ic_neto_positivo": b["lo"] > 0, "trimestres_60": pos_q >= 0.6}
    return {"senales": int(len(tr)), "operaciones": int(len(f)), "sin_llenar": int((~tr["llenada"]).sum()),
            "winrate_tp": float((f["motivo"] == "TP").mean()), "salidas": f["motivo"].value_counts().to_dict(),
            "neto_medio_usd_oz": b["mean"], "ic98_75": [b["lo"], b["hi"]], "R_medio_bruto": float(f["R"].mean()),
            "trimestres_positivos": pos_q, "criterios": crit, "pasa": all(crit.values())}


def evaluate_binary(tr: pd.DataFrame) -> dict:
    if not len(tr):
        return {"operaciones": 0, "pasa": False}
    nt = tr[tr["resultado"] != 0]
    n, w = len(nt), int((nt["resultado"] > 0).sum())
    lo, hi = wilson(w, n) if n else (float("nan"), float("nan"))
    be = 1 / 1.85
    p = binom_pvalue_greater(w, n, be) if n else 1.0
    ev = float(tr["pnl"].mean())
    crit = {"min_300": len(tr) >= 300, "p_bonferroni": p < ALPHA, "wilson": lo > be, "ev_positivo": ev > 0}
    return {"operaciones": int(len(tr)), "sin_empate": n, "aciertos": w, "acierto": w / n if n else None,
            "lo95": float(lo), "hi95": float(hi), "p": p, "ev": ev, "criterios": crit, "pasa": all(crit.values())}


def run(root: Path = Path("data/raw"), out_dir: Path = Path("results/estudio8"), n_boot: int = 2000) -> dict:
    inst = get_instrument("XAUUSD")
    bars_all, quality = to_canonical(store.load(root, inst, source="histdata"), fill_gaps=True)
    ind_all = indicators(bars_all)
    sides = {m: signals(bars_all, ind_all, m) for m in (False, True)}
    report = {"estudio": "Estudio 8 — «Golden BIAS 200» reconstruido (pre-registro dffe312)", "git_sha": git_sha(),
              "costo_usd_oz": COST, "calidad_datos": quality, "fases": {}}
    passing = list(HYPS)
    for phase, (a, b) in PHASES.items():
        lo, hi = pd.Timestamp(a, tz="UTC"), pd.Timestamp(b, tz="UTC")
        m = (bars_all.index >= lo) & (bars_all.index < hi)
        if not m.any():
            report["fases"][phase] = {"nota": "sin datos"}
            break
        bars, ind = bars_all[m], ind_all[m]
        res = {}
        for hname in passing:
            kind, mtf = HYPS[hname]
            side = sides[mtf][m]
            if kind == "contado":
                res[hname] = evaluate_spot(simulate_spot(bars, ind, side), n_boot)
            else:
                res[hname] = evaluate_binary(simulate_binary(bars, side, inst.point))
        report["fases"][phase] = {"periodo": [a, b], "resultados": res}
        passing = [h for h in passing if res[h]["pasa"]]
        if not passing:
            break
    report["pasan_todas_las_fases"] = passing if "B" in report["fases"] and report["fases"]["B"].get("resultados") else []
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "resultado.json").write_text(json.dumps(jsonable(report), indent=2, ensure_ascii=False),
                                            encoding="utf-8")
    return report
