"""Estudio 16: variables parciales hasta el segundo k (sin futuro) y etiquetas con clic L s después."""

import numpy as np
import pandas as pd

from tradingbot.research.study16 import label, minute_table, partial_features


def _sec(n_min=6, seed=0):
    idx = pd.date_range("2024-01-01", periods=n_min * 60, freq="s", tz="UTC")
    rng = np.random.default_rng(seed)
    c = 100 + np.cumsum(rng.normal(0, 0.05, len(idx)))
    return pd.DataFrame({"h": c + 0.02, "l": c - 0.02, "c": c, "v": np.float32(1.0), "tb": np.float32(0.25),
                         "n": np.float32(3.0)}, index=idx)


def test_minute_table_prices_and_partial_window():
    s = _sec()
    minutes = pd.date_range("2024-01-01", periods=3, freq="min", tz="UTC")
    t = minute_table(s, minutes)
    c = s["c"].to_numpy()
    # Minuto 1 (empieza en el segundo 60): P55 = cierre del segundo 54 del minuto.
    assert np.isclose(t["P55"].iloc[1], c[60 + 54]) and np.isclose(t["P55_m10"].iloc[1], c[60 + 44])
    assert np.isclose(t["hi50"].iloc[1], s["h"].iloc[60:110].max())
    assert np.isclose(t["tib10_55"].iloc[1], 2 * 0.25 - 1) and np.isclose(t["vol10_55"].iloc[1], 10 / 55)
    # Etiqueta de H16a: entrada antes de t+60 s (cierre del segundo 59), salida antes de t+120 s.
    assert np.isclose(t["Q60"].iloc[1], c[60 + 59]) and np.isclose(t["Q120"].iloc[1], c[60 + 119])
    d = label(t, 55, 5)
    assert d[1] == np.sign(np.round((c[60 + 119] - c[60 + 59]) / 0.005))


def test_partial_features_ignore_seconds_after_k():
    s = _sec(seed=1)
    minutes = pd.date_range("2024-01-01", periods=3, freq="min", tz="UTC")
    s2 = s.copy()
    s2.iloc[60 + 55:, :3] += 50.0  # todo lo que pasa desde el segundo 55 del minuto 1
    t1, t2 = minute_table(s, minutes), minute_table(s2, minutes)
    o = pd.Series(100.0, index=minutes)
    vol = pd.Series(0.001, index=minutes)
    f1, f2 = partial_features(t1, o, vol, 55), partial_features(t2, o, vol, 55)
    pd.testing.assert_series_equal(f1.iloc[1], f2.iloc[1])
    assert not np.isclose(t1["Q60"].iloc[1], t2["Q60"].iloc[1])  # la etiqueta sí cambia (es futuro)


def test_missing_seconds_and_large_gaps():
    s = _sec()
    s = s.drop(s.index[60 + 10:60 + 30])  # 20 segundos sin vela en el minuto 1
    minutes = pd.date_range("2024-01-01", periods=3, freq="min", tz="UTC")
    t = minute_table(s, minutes)
    f = partial_features(t, pd.Series(100.0, index=minutes), pd.Series(0.001, index=minutes), 50)
    assert t["faltan50"].iloc[1] == 20 and f.iloc[1].isna().all()
    # Un hueco de más de 5 s antes del instante pedido deja el precio en NaN.
    assert np.isnan(t["P50_m20"].iloc[1])
