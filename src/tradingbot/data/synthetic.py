"""Datos SINTÉTICOS para pruebas y demostraciones. NUNCA se usan para conclusiones de mercado.

Permiten controles positivos y negativos del pipeline:
- phi = 0   → paseo aleatorio: el pipeline debe concluir «sin señal» (control negativo).
- phi ≠ 0   → autocorrelación sembrada: el pipeline debe detectarla (control positivo).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.signal import lfilter


def generate(start: str = "2023-01-02", days: int = 60, phi: float = 0.0, seed: int = 7,
             base_price: float = 1.10, point: float = 1e-5, spread_pips: float = 0.2,
             no_tick_prob: float = 0.03) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.date_range(pd.Timestamp(start, tz="UTC"), periods=days * 1440, freq="min", name="time")
    # Mercado cerrado: viernes 21:00 UTC → domingo 21:00 UTC.
    dow, hour = idx.dayofweek, idx.hour
    closed = ((dow == 4) & (hour >= 21)) | (dow == 5) | ((dow == 6) & (hour < 21))
    idx = idx[~closed]
    n = len(idx)
    # Estacionalidad intradía de la volatilidad (más alta en Londres/Nueva York).
    h = idx.hour.to_numpy() + idx.minute.to_numpy() / 60
    season = 0.6 + 0.8 * np.exp(-((h - 13.5) ** 2) / 8) + 0.3 * np.exp(-((h - 8) ** 2) / 4)
    sigma = 0.35e-4 * season  # ≈ 0,35 pips por minuto en horas tranquilas
    eps = rng.standard_normal(n)
    r = lfilter([1.0], [1.0, -phi], sigma * eps)  # AR(1): r_t = phi·r_{t−1} + σ_t·ε_t
    no_tick = rng.random(n) < no_tick_prob
    r[no_tick] = 0.0
    close = base_price * np.exp(np.cumsum(r))
    close = np.round(close / point) * point
    open_ = np.concatenate(([base_price], close[:-1]))
    wig = np.abs(rng.standard_normal(n)) * sigma * base_price * 0.5
    high = np.maximum(open_, close) + np.where(no_tick, 0, np.round(wig / point) * point)
    low = np.minimum(open_, close) - np.where(no_tick, 0, np.round(wig / point) * point)
    spread = np.round((spread_pips * 1e-4 * (1 + 0.3 * rng.random(n))) / point) * point
    half = spread / 2
    df = pd.DataFrame(index=idx)
    for side, sgn in (("bid", -1), ("ask", 1)):
        df[f"{side}_o"] = open_ + sgn * half
        df[f"{side}_h"] = high + sgn * half
        df[f"{side}_l"] = low + sgn * half
        df[f"{side}_c"] = close + sgn * half
    vol = np.where(no_tick, 0.0, rng.gamma(2.0, 1.0, n) * season)
    df["bid_v"] = vol
    df["ask_v"] = vol
    return df
