"""Estudio 37: evaluación con el resultado de otra bolsa (empates fuera del acierto)."""

import numpy as np
import pandas as pd

from tradingbot.research.study37 import evaluate


def test_evaluate_counts_ties_out_of_accuracy():
    t = pd.DatetimeIndex(["2026-01-01 00:00", "2026-01-01 00:01", "2026-01-01 00:02", "2026-01-01 00:03"], tz="UTC")
    r = evaluate(np.array([1, -1, 1, 1]), np.array([1.0, -1.0, 0.0, np.nan]), t)
    assert r["operaciones"] == 3 and r["acierto"] == 1.0
