"""Particiones cronológicas walk-forward con purga, y bloqueo del periodo final.

Para cada tramo de prueba [test_start, test_end):
  entrenamiento = [test_start − train_months, test_start)
  ajuste        = primer (1 − calib_frac) del entrenamiento; calibración = el resto
Purga: una muestra solo puede estar en un tramo si su etiqueta termina (label_end) antes del inicio
del tramo siguiente. Así ninguna etiqueta de ajuste/calibración se solapa con la prueba.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class Fold:
    name: str
    train_start: pd.Timestamp
    calib_start: pd.Timestamp
    test_start: pd.Timestamp
    test_end: pd.Timestamp

    def masks(self, times: pd.DatetimeIndex, label_end: pd.Series | np.ndarray):
        t = times
        le = pd.DatetimeIndex(label_end)
        fit = (t >= self.train_start) & (t < self.calib_start) & (le <= self.calib_start)
        cal = (t >= self.calib_start) & (t < self.test_start) & (le <= self.test_start)
        test = (t >= self.test_start) & (t < self.test_end) & (le <= self.test_end)
        return np.asarray(fit), np.asarray(cal), np.asarray(test)


class HoldoutLocked(Exception):
    pass


def make_folds(test_start: str, test_end: str, step_months: int = 3, train_months: int = 12,
               calib_frac: float = 0.2) -> list[Fold]:
    folds = []
    s = pd.Timestamp(test_start, tz="UTC")
    end = pd.Timestamp(test_end, tz="UTC")
    while s < end:
        e = min(s + pd.DateOffset(months=step_months), end)
        tr = s - pd.DateOffset(months=train_months)
        cal = tr + (s - tr) * (1 - calib_frac)
        cal = cal.floor("D")
        folds.append(Fold(f"{s:%Y-%m}", tr, cal, s, e))
        s = e
    return folds


def stage_folds(stage: str, cfg: dict) -> list[Fold]:
    if stage == "dev":
        return make_folds(cfg["dev_test_start"], cfg["holdout_start"], cfg["step_months"],
                          cfg["train_months"], cfg["calib_frac"])
    if stage == "holdout":
        return make_folds(cfg["holdout_start"], cfg["holdout_end"], cfg["step_months"],
                          cfg["train_months"], cfg["calib_frac"])
    raise ValueError("stage debe ser 'dev' o 'holdout'")


def enforce_lock(bars: pd.DataFrame, stage: str, cfg: dict) -> pd.DataFrame:
    """En la etapa de desarrollo se ELIMINAN todas las velas del periodo bloqueado antes de calcular nada."""
    hs = pd.Timestamp(cfg["holdout_start"], tz="UTC")
    he = pd.Timestamp(cfg["holdout_end"], tz="UTC")
    if stage == "dev":
        out = bars[bars.index < hs]
        if len(out) and out.index.max() >= hs:  # pragma: no cover - defensa adicional
            raise HoldoutLocked("Datos del periodo bloqueado en la etapa de desarrollo")
        return out
    return bars[bars.index < he]
