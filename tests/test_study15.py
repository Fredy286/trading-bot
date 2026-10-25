"""Estudio 15: resumen por minuto de las velas de 1 s, según el pre-registro."""

import numpy as np
import pandas as pd

from tradingbot.research.study15 import minute_summary, sec_features


def _sec(n_min=3):
    idx = pd.date_range("2024-01-01", periods=n_min * 60, freq="s", tz="UTC")
    c = 100 + 0.01 * np.arange(len(idx))
    return pd.DataFrame({"c": c, "volume": 1.0, "trades": 2.0, "taker_buy_base": 0.75}, index=idx)


def test_minute_summary_uses_the_last_seconds_of_each_minute():
    s = _sec()
    m = minute_summary(s)
    assert len(m) == 3 and m.index[1] == pd.Timestamp("2024-01-01 00:01", tz="UTC")
    c = s["c"].to_numpy()
    assert np.isclose(m["lr10"].iloc[1], np.log(c[119] / c[109]))
    assert np.isclose(m["s_tib10"].iloc[0], 2 * 0.75 - 1) and np.isclose(m["s_vol10"].iloc[0], 10 / 60)
    assert np.isclose(m["s_n10"].iloc[0], 1 / 6) and (m["faltan"] == 0).all()


def test_missing_seconds_are_filled_and_counted():
    s = _sec().drop(pd.date_range("2024-01-01 00:00:55", periods=5, freq="s", tz="UTC"))
    m = minute_summary(s)
    assert m["faltan"].iloc[0] == 5
    # Sin velas en 55–59, el cierre del segundo 59 es el del segundo 54.
    c54 = s["c"].loc["2024-01-01 00:00:54"]
    assert np.isclose(m["lr5"].iloc[0], 0.0) and np.isclose(m["lr10"].iloc[0], np.log(c54 / s["c"].iloc[49]))


def test_sec_features_are_normalized_and_drop_minutes_with_many_gaps():
    s = _sec()
    s = s.drop(pd.date_range("2024-01-01 00:02:00", periods=20, freq="s", tz="UTC"))
    m = minute_summary(s)
    idx = m.index
    f = sec_features(idx, m, pd.Series(0.001, index=idx))
    assert np.isclose(f["s_r20"].iloc[0], m["lr20"].iloc[0] / (0.001 * np.sqrt(20 / 60)))
    assert f.iloc[2].isna().all()  # 20 segundos sin vela > 10 permitidos
