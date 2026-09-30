"""Métricas estadísticas: intervalos de Wilson, pruebas binomiales, bootstrap por bloques,
reducción máxima, corrección de Holm y medidas de calibración."""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import binomtest


def wilson(k, n, z: float = 1.96):
    """Intervalo de Wilson para una proporción (vectorizado). Devuelve (lo, hi); NaN si n = 0."""
    k = np.asarray(k, float)
    n = np.asarray(n, float)
    with np.errstate(invalid="ignore", divide="ignore"):
        p = k / n
        den = 1 + z**2 / n
        centre = (p + z**2 / (2 * n)) / den
        half = z * np.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / den
        lo = np.where(n > 0, centre - half, np.nan)
        hi = np.where(n > 0, centre + half, np.nan)
    if lo.ndim == 0:
        return float(lo), float(hi)
    return lo, hi


def binom_pvalue_greater(k: int, n: int, p0: float) -> float:
    """P-valor unilateral H0: acierto ≤ p0 frente a H1: acierto > p0."""
    if n <= 0:
        return 1.0
    return float(binomtest(int(k), int(n), p0, alternative="greater").pvalue)


def block_bootstrap_mean(values: np.ndarray, blocks: np.ndarray, n_boot: int = 1000,
                         seed: int = 12345) -> dict:
    """IC 95 % de la media remuestreando bloques completos (p. ej., días) para respetar dependencia.

    Devuelve media, IC y p-valor unilateral aproximado de H0: media ≤ 0.
    """
    values = np.asarray(values, float)
    if len(values) == 0:
        return {"mean": np.nan, "lo": np.nan, "hi": np.nan, "p_le_0": 1.0}
    codes, uniq = pd.factorize(blocks)
    k = len(uniq)
    sums = np.bincount(codes, weights=values, minlength=k)
    cnts = np.bincount(codes, minlength=k).astype(float)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, k, size=(n_boot, k))
    bs = sums[idx].sum(axis=1) / np.maximum(cnts[idx].sum(axis=1), 1)
    mean = values.mean()
    lo, hi = np.quantile(bs, [0.025, 0.975])
    # p-valor por desplazamiento: distribución centrada en 0 bajo H0.
    p = float((np.sum(bs - mean >= mean) + 1) / (n_boot + 1))
    return {"mean": float(mean), "lo": float(lo), "hi": float(hi), "p_le_0": p}


def max_drawdown(pnl: np.ndarray) -> float:
    """Máxima caída desde un pico de la curva acumulada (en las mismas unidades que pnl)."""
    pnl = np.asarray(pnl, float)
    if len(pnl) == 0:
        return 0.0
    eq = np.concatenate(([0.0], np.cumsum(pnl)))
    peak = np.maximum.accumulate(eq)
    return float(np.max(peak - eq))


def holm(pvalues: list[float]) -> list[float]:
    """P-valores ajustados por Holm–Bonferroni (controla el error de familia)."""
    p = np.asarray(pvalues, float)
    m = len(p)
    if m == 0:
        return []
    order = np.argsort(p)
    adj = np.empty(m)
    running = 0.0
    for rank, i in enumerate(order):
        running = max(running, (m - rank) * p[i])
        adj[i] = min(1.0, running)
    return adj.tolist()


def brier(p: np.ndarray, y: np.ndarray) -> float:
    return float(np.mean((np.asarray(p) - np.asarray(y)) ** 2))


def log_loss(p: np.ndarray, y: np.ndarray, eps: float = 1e-6) -> float:
    p = np.clip(np.asarray(p, float), eps, 1 - eps)
    y = np.asarray(y, float)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def reliability(p: np.ndarray, y: np.ndarray, n_bins: int = 10) -> tuple[pd.DataFrame, float]:
    """Tabla de confiabilidad con bins de igual frecuencia y ECE (error de calibración esperado)."""
    p = np.asarray(p, float)
    y = np.asarray(y, float)
    if len(p) == 0:
        return pd.DataFrame(), float("nan")
    q = np.unique(np.quantile(p, np.linspace(0, 1, n_bins + 1)))
    b = np.clip(np.searchsorted(q, p, side="right") - 1, 0, max(len(q) - 2, 0))
    rows = []
    ece = 0.0
    for i in range(max(len(q) - 1, 1)):
        m = b == i
        if not m.any():
            continue
        n = int(m.sum())
        pm, ym = float(p[m].mean()), float(y[m].mean())
        lo, hi = wilson(ym * n, n)
        rows.append({"bin": i, "n": n, "p_pred": pm, "freq_obs": ym, "obs_lo95": lo, "obs_hi95": hi})
        ece += n / len(p) * abs(pm - ym)
    return pd.DataFrame(rows), float(ece)
