"""Estudio 20: evaluación con desglose mensual y umbral de confianza."""

import numpy as np
import pandas as pd

from tradingbot.research.contracts import BinaryContract
from tradingbot.research.study20 import evaluate


def test_monthly_breakdown_and_threshold():
    times = pd.DatetimeIndex(["2026-01-05 10:00", "2026-01-06 10:00", "2026-02-02 10:00", "2026-02-03 10:00"],
                             tz="UTC")
    p = np.array([0.70, 0.30, 0.57, 0.65])
    d = np.array([1.0, -1.0, -1.0, 1.0])  # gana, gana, pierde, gana
    q = np.zeros(4)
    r = evaluate(p, d, q, times, BinaryContract(0.85, "refund"), 0.02, 50, 0.95)
    assert r["operaciones"] == 4 and r["mensual"]["2026-01"]["acierto"] == 1.0
    assert r["mensual"]["2026-02"]["acierto"] == 0.5 and r["meses_ev_positivo"] == 0.5  # febrero: 1 de 2, EV < 0
    alto = evaluate(p, d, q, times, BinaryContract(0.85, "refund"), 0.02, 50, 0.95, umbral=0.60)
    assert alto["operaciones"] == 3 and alto["acierto"] == 1.0
