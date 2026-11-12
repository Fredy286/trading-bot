"""Apilado genérico (el método del Estudio 63) para otros contratos: metamodelo logístico mes a mes, solo con el pasado.

Lo usan los Estudios 66 (blitz de BTC de IQ Option) y 67 (OKX 15 min). El Estudio 63 conserva su propio código congelado.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import study63 as s63


def walk_forward(df: pd.DataFrame, opiniones: tuple[str, ...], ajustar: np.ndarray | None = None,
                 meses=tuple(s63.PRUEBA)) -> tuple[pd.Series, dict]:
    """Probabilidad del metamodelo en los meses de prueba. `ajustar`: filas válidas para ajustar (p. ej., sin empates).
    La etiqueta es df["y"] (> 0 = sube)."""
    mes = np.asarray(df.index.tz_convert(None).to_period("M").astype(str))
    X = s63.logit(df[list(opiniones)].to_numpy())
    y = (df["y"].to_numpy() > 0).astype(float)
    ajustar = np.ones(len(df), bool) if ajustar is None else ajustar
    out, coefs = pd.Series(np.nan, index=df.index), {}
    for m in meses:
        ini = pd.Timestamp(m + "-01", tz="UTC")
        train = np.asarray(df.index < ini - s63.PURGA) & ajustar
        test = mes == m
        if train.sum() < 1000 or not test.any():
            continue
        b = s63.logistica(X[train], y[train])
        out[test] = s63.predecir(b, X[test])
        coefs[m] = dict(zip(("constante", *opiniones), (float(x) for x in b)))
    return out, coefs


def semanas(index: pd.DatetimeIndex) -> np.ndarray:
    iso = index.isocalendar()
    return (iso["year"].astype(int) * 100 + iso["week"].astype(int)).to_numpy()


def comparar(gg: np.ndarray, gb: np.ndarray, index: pd.DatetimeIndex, n_boot: int, seed: int) -> dict:
    """ΔG = ganancia del gran bot − la de la base, con el cuantil 5 % de remuestreos pareados por semanas ISO."""
    d = s63._boot_semanas(gg - gb, semanas(index), n_boot, seed)
    return {"delta_ganancia": float(gg.sum() - gb.sum()), "limite_inferior_5": float(np.quantile(d, 0.05)),
            "p_bootstrap": float((d <= 0).mean())}
