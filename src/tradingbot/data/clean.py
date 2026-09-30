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


def to_canonical(raw: pd.DataFrame, closed_run_minutes: int = 30) -> tuple[pd.DataFrame, dict]:
    if raw.empty:
        raise ValueError("Datos vacíos")
    raw = raw.sort_index()
    raw = raw[~raw.index.duplicated(keep="last")]
    grid = pd.date_range(raw.index[0].floor("min"), raw.index[-1].floor("min"), freq="min", tz="UTC", name="time")
    r = raw.reindex(grid)
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

    report: dict = {"grid_minutes": int(len(grid)), "present_minutes": int(df["c"].notna().sum())}

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
    report["session_minutes"] = int(valid.sum())
    report["first"] = df.index[valid.to_numpy()].min().isoformat() if valid.any() else None
    report["last"] = df.index[valid.to_numpy()].max().isoformat() if valid.any() else None
    if valid.any():
        sp = df.loc[valid, "spread_c"]
        report["spread_median"] = float(sp.median())
        report["spread_p95"] = float(sp.quantile(0.95))
    return df, report
