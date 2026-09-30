"""Limpieza y forma canónica de las velas.

Salida: rejilla completa de minutos UTC con columnas
  o, h, l, c        precio medio (bid+ask)/2 de apertura, máximo, mínimo y cierre
  spread_o, spread_c  spread (ask − bid) en la apertura y el cierre de la vela
  volume            volumen del proveedor (FX: solo la liquidez de Dukascopy; cripto: volumen real)
  no_tick           True si en el minuto no hubo ticks (precio sin cambio)
Las filas con mercado cerrado (rachas ≥ `closed_run_minutes` sin ticks) quedan en NaN: no son
decisiones posibles ni resultados evaluables. Nada se rellena hacia adelante.
Nota: el máximo/mínimo «medio» se aproxima como promedio de máximos/mínimos bid y ask.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def _run_lengths(mask: np.ndarray) -> np.ndarray:
    """Para cada posición True, la longitud de la racha de True a la que pertenece (0 si False)."""
    n = len(mask)
    out = np.zeros(n, dtype=np.int64)
    if n == 0:
        return out
    m = mask.astype(np.int8)
    change = np.flatnonzero(np.diff(np.concatenate(([0], m, [0]))))
    lengths = change[1::2] - change[0::2]
    out[mask.astype(bool)] = np.repeat(lengths, lengths)
    return out


def to_canonical(raw: pd.DataFrame, closed_run_minutes: int = 30, fill_gaps: bool = False) -> tuple[pd.DataFrame, dict]:
    """`fill_gaps=True` para fuentes que OMITEN los minutos sin ticks (HistData): los huecos más
    cortos que `closed_run_minutes` se rellenan con velas planas al último cierre conocido."""
    if raw.empty:
        raise ValueError("Datos vacíos")
    raw = raw.sort_index()
    raw = raw[~raw.index.duplicated(keep="last")]
    grid = pd.date_range(raw.index[0].floor("min"), raw.index[-1].floor("min"), freq="min", tz="UTC", name="time")
    r = raw.reindex(grid)
    filled = 0
    if fill_gaps:
        missing = r["bid_c"].isna().to_numpy()
        short = missing & (_run_lengths(missing) < closed_run_minutes)
        filled = int(short.sum())
        for side in ("bid", "ask"):
            prev = r[f"{side}_c"].ffill()  # último cierre conocido (pasado)
            for k in ("o", "h", "l", "c"):
                r.loc[short, f"{side}_{k}"] = prev[short]
        for col in ("bid_v", "ask_v"):
            if col in r:
                r.loc[short, col] = 0.0
        if "trades" in r:
            r.loc[short, "trades"] = 0.0
    df = pd.DataFrame(index=grid)
    for k in ("o", "h", "l", "c"):
        df[k] = (r[f"bid_{k}"] + r[f"ask_{k}"]) / 2.0
    df["spread_o"] = r["ask_o"] - r["bid_o"]
    df["spread_c"] = r["ask_c"] - r["bid_c"]
    vol = r.get("bid_v", 0.0) + r.get("ask_v", 0.0)
    df["volume"] = vol
    if "trades" in r:
        no_tick = r["trades"].fillna(0) <= 0
    else:
        no_tick = vol.fillna(0) <= 0
    df["no_tick"] = no_tick & df["c"].notna()

    report: dict = {"grid_minutes": int(len(grid)), "present_minutes": int(df["c"].notna().sum()),
                    "filled_no_tick_minutes": filled}

    neg = df["spread_o"].lt(0) | df["spread_c"].lt(0)
    report["negative_spread_minutes"] = int(neg.sum())
    df.loc[neg, ["o", "h", "l", "c", "spread_o", "spread_c"]] = np.nan

    idle = (df["no_tick"] | df["c"].isna()).to_numpy()
    runs = _run_lengths(idle)
    closed = runs >= closed_run_minutes
    report["closed_minutes"] = int(closed.sum())
    report["isolated_no_tick_minutes"] = int((df["no_tick"].to_numpy() & ~closed).sum())
    df.loc[closed, ["o", "h", "l", "c", "spread_o", "spread_c", "volume"]] = np.nan
    df["no_tick"] = df["no_tick"] & ~closed

    valid = df["c"].notna()
    report["unexpected_gaps"] = unexpected_gaps(df.index, ~valid.to_numpy())
    report["session_minutes"] = int(valid.sum())
    report["first"] = df.index[valid.to_numpy()].min().isoformat() if valid.any() else None
    report["last"] = df.index[valid.to_numpy()].max().isoformat() if valid.any() else None
    if valid.any():
        sp = df.loc[valid, "spread_c"]
        report["spread_median"] = float(sp.median())
        report["spread_p95"] = float(sp.quantile(0.95))
    return df, report


def unexpected_gaps(index: pd.DatetimeIndex, missing: np.ndarray, min_minutes: int = 120, top: int = 10) -> dict:
    """Huecos ≥ `min_minutes` que NO empiezan en el cierre habitual de fin de semana
    (viernes ≥ 20:00 UTC, sábado o domingo). Útil para detectar meses faltantes del proveedor."""
    m = missing.astype(np.int8)
    change = np.flatnonzero(np.diff(np.concatenate(([0], m, [0]))))
    starts, ends = change[0::2], change[1::2]
    rows = []
    for s_, e_ in zip(starts, ends):
        if e_ - s_ < min_minutes or s_ == 0 or e_ == len(index):
            continue
        t = index[s_]
        weekend = (t.dayofweek == 4 and t.hour >= 20) or t.dayofweek >= 5
        if not weekend:
            rows.append((int(e_ - s_), t.isoformat(), index[e_ - 1].isoformat()))
    rows.sort(reverse=True)
    return {"count": len(rows), "total_minutes": int(sum(r[0] for r in rows)),
            "largest": [{"minutes": r[0], "from": r[1], "to": r[2]} for r in rows[:top]]}
