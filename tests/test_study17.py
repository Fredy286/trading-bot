"""Estudio 17: zigzag causal, eventos por zona de Fibonacci y variables ICT."""

import numpy as np
import pandas as pd

from tradingbot.research.study17 import ict_features, zigzag, zone_events


def test_zigzag_confirms_swings_only_after_the_threshold_and_is_causal():
    c = np.r_[np.linspace(100, 110, 11), np.linspace(109, 104, 6), np.linspace(105, 112, 8)]
    h, l = c + 0.1, c - 0.1
    thr = np.full(len(c), 3.0)
    imps, fib = zigzag(h, l, c, thr)
    # El máximo de 110,1 se confirma cuando el cierre baja a ≤ 110,1 − 3 = 107,1 (vela 13, cierre 107).
    up = [i for i in imps if i[0] == 1]
    assert up and np.isclose(up[0][2], 110.1) and up[0][3] == 13
    # Causal: cambiar lo que pasa después de t no cambia fib_r hasta t.
    c2 = c.copy()
    c2[18:] = 90
    _, fib2 = zigzag(c2 + 0.1, c2 - 0.1, c2, thr)
    assert np.allclose(fib[:18], fib2[:18])
    assert fib[16] > 0  # retroceso de un impulso alcista


def test_zone_events_measure_continuation_from_the_first_touch():
    # Impulso alcista 100 → 110; retroceso hasta 104,5 (55 %: toca Z1 y Z2) y luego sube a 111.
    c = np.r_[np.linspace(100, 110, 11), [107.0, 106.0, 105.0, 104.5, 106, 108, 111]]
    h, l = c + 0.05, c - 0.05
    imps, _ = zigzag(h, l, c, np.full(len(c), 2.5))
    ev = zone_events(h, l, imps, pd.date_range("2024-01-01", periods=len(c), freq="15min", tz="UTC"))
    assert set(ev["zona"]) == {"Z2"} or set(ev["zona"]) <= {"Z1", "Z2"}
    assert (ev["acierto"] == 1.0).all()


def test_ict_features_follow_definitions():
    n = 400
    idx = pd.date_range("2024-01-01", periods=n, freq="min", tz="UTC")
    c = 100 + np.sin(np.arange(n) / 10)
    b = pd.DataFrame({"o": c, "h": c + 0.05, "l": c - 0.05, "c": c}, index=idx)
    t = 300
    b.iloc[t, b.columns.get_loc("h")] = b["h"].iloc[t - 60:t].max() + 1  # barre el máximo de 60 y cierra dentro
    f = ict_features(b, pd.Series(0.001, index=idx))
    assert f["ict_sweep_hi"].iloc[t] == 1 and f["ict_bos"].iloc[t] == 0
    assert 0 <= f["ict_pd"].iloc[t] <= 1 and f["ict_eqh"].iloc[t] >= 0
    b2 = b.copy()
    b2.iloc[t + 1:, :] += 50  # el futuro no cambia la fila t
    f2 = ict_features(b2, pd.Series(0.001, index=idx))
    pd.testing.assert_series_equal(f.iloc[t], f2.iloc[t])
