"""Etiquetas de dirección a horizonte fijo (definición exacta en el protocolo, sección 1).

Decisión al cierre de la vela t (τ = t + 60 s). Entrada: apertura de la vela t+d. Salida: cierre de
la vela t+d+h−1. Si falta cualquier vela entre entrada y salida → no evaluable (NaN).
Empate: movimiento nulo a la resolución de medio punto (el precio medio tiene medio punto de resolución).
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def make_labels(bars: pd.DataFrame, horizon: int, entry_delay: int, point: float) -> pd.DataFrame:
    if horizon < 1 or entry_delay < 1:
        raise ValueError("horizon y entry_delay deben ser ≥ 1")
    n_fwd = entry_delay + horizon - 1
    entry = bars["o"].shift(-entry_delay)
    exit_ = bars["c"].shift(-n_fwd)
    present = bars["c"].notna().astype(np.int8)
    window_ok = present.rolling(horizon, min_periods=horizon).sum().shift(-n_fwd) == horizon
    ok = window_ok & entry.notna() & exit_.notna()

    move = exit_ - entry
    half_points = np.round(move.to_numpy() / (point / 2.0))
    direction = np.sign(half_points)
    direction = np.where(ok.to_numpy(), direction, np.nan)

    sp_in = bars["spread_o"].shift(-entry_delay)
    sp_out = bars["spread_c"].shift(-n_fwd)
    # Contado: largo compra al ASK de entrada y vende al BID de salida; corto al revés.
    long_px = move - sp_in / 2 - sp_out / 2
    short_px = -move - sp_in / 2 - sp_out / 2

    out = pd.DataFrame(index=bars.index)
    out["entry"] = entry.where(ok)
    out["exit"] = exit_.where(ok)
    out["move"] = move.where(ok)
    out["dir"] = direction
    out["long_px"] = long_px.where(ok)
    out["short_px"] = short_px.where(ok)
    out["spread_in"] = sp_in.where(ok)
    # Momento en que el resultado se conoce: fin de la vela de salida.
    out["label_end"] = bars.index + pd.Timedelta(minutes=n_fwd + 1)
    return out


def decision_mask(index: pd.DatetimeIndex, horizon: int) -> np.ndarray:
    """Muestreo no solapado: para h>1 solo se decide en minutos múltiplos de h (reloj UTC)."""
    if horizon == 1:
        return np.ones(len(index), dtype=bool)
    mod = (index.hour * 60 + index.minute).to_numpy()
    return (mod % horizon) == 0
