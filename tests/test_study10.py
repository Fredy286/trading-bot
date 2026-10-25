"""Estudio 10: DXY aproximado, zonas causales y entrada 1 min después del cierre de 15 min."""

import numpy as np
import pandas as pd

from tradingbot.research.study10 import dxy_close, filter_effect, simulate, to_15m, zones


def test_dxy_proxy_uses_ice_weights_renormalized():
    idx = pd.date_range("2024-01-01", periods=3, freq="min", tz="UTC")
    fx = {"EURUSD": pd.Series([1.10, 1.10, 1.21], index=idx), "USDJPY": pd.Series(150.0, index=idx),
          "GBPUSD": pd.Series(1.25, index=idx)}
    d = dxy_close(fx)
    # Si el euro sube 10 %, el DXY* baja en la proporción de su peso renormalizado (0,576/0,831).
    assert np.isclose(np.log(d.iloc[2] / d.iloc[0]), -0.576 / 0.831 * np.log(1.1))
    fx["USDJPY"] = fx["USDJPY"].drop(idx[1])
    assert np.isnan(dxy_close(fx).iloc[1])


def test_zones_use_only_previous_candles():
    idx = pd.date_range("2024-01-01", periods=200, freq="15min", tz="UTC")
    c = 100 + np.sin(np.arange(200) / 5)
    b = pd.DataFrame({"o": c, "h": c + 0.2, "l": c - 0.2, "c": c}, index=idx)
    z = zones(b)
    b2 = b.copy()
    b2.iloc[151:] -= 50  # derrumbe después de t = 150
    pd.testing.assert_frame_equal(z.iloc[:151], zones(b2).iloc[:151])


def test_entry_is_one_minute_after_the_15m_close_and_trades_do_not_overlap():
    idx = pd.date_range("2024-01-01 10:00", periods=120, freq="min", tz="UTC")
    c = np.arange(120, dtype=float) + 100
    gold1 = pd.DataFrame({"o": c - 0.5, "h": c, "l": c - 1, "c": c}, index=idx)
    side = pd.Series(0, index=pd.date_range("2024-01-01 10:00", periods=8, freq="15min", tz="UTC"))
    side.iloc[0] = side.iloc[1] = 1
    tr = simulate(gold1, side, 15)
    # Vela 10:00–10:15: entrada en la apertura de 10:16 y salida al cierre de 10:30; la de 10:15 se solapa.
    assert len(tr) == 1 and tr.iloc[0]["resultado"] == 1
    assert len(simulate(gold1, side, 1)) == 2  # con 1 min ya no se solapan


def test_filter_effect_compares_kept_and_removed_trades():
    t = pd.date_range("2024-01-01", periods=4, freq="1h", tz="UTC")
    zone_tr = pd.DataFrame({"time": t, "lado": [1, 1, -1, -1], "resultado": [1, -1, 1, -1], "pnl": 0.0})
    full = pd.Series([1, 0, -1, 0], index=t)
    e = filter_effect(zone_tr, full, n_boot=50)
    assert e["pasan_filtro"] == 2 and e["acierto_pasan"] == 1.0 and e["acierto_quitadas"] == 0.0
    assert e["perdedoras_evitadas"] == 1.0 and e["ganadoras_perdidas"] == 0.0
