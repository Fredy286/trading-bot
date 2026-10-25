"""Estudio 8: reglas reconstruidas del «Golden BIAS 200», sin información futura."""

import numpy as np
import pandas as pd

from tradingbot.research.study8 import (COST, in_session, indicators, mtf_arrows, signals, simulate_binary,
                                        simulate_spot)


def _bars(c, start="2024-03-04 14:00"):
    c = np.asarray(c, float)
    idx = pd.date_range(start, periods=len(c), freq="min", tz="UTC")
    o = np.r_[c[0], c[:-1]]
    return pd.DataFrame({"o": o, "h": np.maximum(o, c) + 0.05, "l": np.minimum(o, c) - 0.05, "c": c,
                         "spread_o": 0.25, "spread_c": 0.25}, index=idx)


def test_sessions_are_in_mexico_city_time():
    # México no tiene horario de verano desde 2022: UTC−6. 14:00 UTC = 08:00 en México.
    idx = pd.DatetimeIndex(["2024-03-04 13:58", "2024-03-04 13:59", "2024-03-04 17:59", "2024-03-04 18:00",
                            "2024-03-04 23:29", "2024-03-05 05:00"], tz="UTC")
    # Cierre de la vela = apertura + 1 min. 05:01 UTC = 23:01 del día anterior en México: fuera.
    assert in_session(idx).tolist() == [False, True, False, False, True, False]


def test_mtf_arrows_only_use_closed_candles():
    b = _bars(np.linspace(100, 130, 2000))
    a = mtf_arrows(b, 15)
    b2 = b.copy()
    b2.iloc[1501:, b2.columns.get_loc("c")] = 50.0  # derrumbe después de t = 1500
    a2 = mtf_arrows(b2, 15)
    assert np.array_equal(a[:1501], a2[:1501], equal_nan=True)
    assert a[1500] == 1


def test_signal_needs_trend_distance_bullish_candle_and_session():
    c = np.r_[np.full(200, 100.0), np.linspace(100, 110, 300)]
    b = _bars(c, start="2024-03-04 07:00")
    ind = indicators(b)
    s = signals(b, ind, mtf=False)
    t = 450  # 14:30 UTC = 08:31 en México (sesión de Nueva York)
    assert s[t] == 1  # tendencia, distancia ≥ 1 ATR y vela alcista
    assert signals(_bars(c, start="2024-03-04 14:00"), ind, mtf=False)[t] == 0  # 21:30 UTC: fuera de sesión
    b.iloc[t, b.columns.get_loc("o")] = b["c"].iloc[t] + 0.01  # vela bajista
    assert signals(b, indicators(b), mtf=False)[t] == 0


def test_spot_fills_on_pullback_and_counts_sl_first_in_the_same_candle():
    c = np.r_[np.full(200, 100.0), np.linspace(100, 110, 101), np.full(60, 110.0)]
    b = _bars(c)
    ind = indicators(b)
    side = np.zeros(len(b), int)
    t = 300
    side[t] = 1
    lim = ind["sma15"].iloc[t] + 0.25 * ind["atr"].iloc[t]
    assert lim < b["c"].iloc[t]  # hay que esperar el retroceso
    flat = b.columns.get_indexer(["o", "h", "l", "c"])
    b.iloc[t + 1:, flat] = lim + 0.01  # precio quieto justo encima del límite: sin TP ni SL naturales
    b.iloc[t + 3, b.columns.get_loc("l")] = lim - 0.01  # la vela t+3 toca el límite
    b.iloc[t + 6, b.columns.get_loc("h")] = lim + 100  # TP más adelante
    tr = simulate_spot(b, ind, side)
    r = tr.iloc[0]
    assert r["llenada"] and np.isclose(r["entrada"], lim)
    assert r["motivo"] == "TP" and np.isclose(r["neto"], (r["salida"] - r["entrada"]) - COST)
    # Si en la misma vela se tocan SL y TP, cuenta el SL.
    b.iloc[t + 6, b.columns.get_loc("l")] = lim - 100
    assert simulate_spot(b, ind, side).iloc[0]["motivo"] == "SL"
    # Sin retroceso en 10 velas: no hay operación.
    b2 = _bars(c)
    b2.iloc[t + 1:, flat] = lim + 0.5
    assert not simulate_spot(b2, ind, side).iloc[0]["llenada"]


def test_binary_has_no_overlap_and_enters_one_minute_later():
    c = np.r_[np.full(10, 100.0), 100.0, 100.0, 101.0, 101.0, 101.0, 101.0, 102.0, np.full(10, 102.0)]
    b = _bars(c)
    side = np.zeros(len(b), int)
    side[10] = side[12] = side[17] = 1
    tr = simulate_binary(b, side, point=0.001)
    assert tr["t"].tolist() == [10, 17]  # la de t = 12 se solapa con la de t = 10 (vence en t+6)
    # Entrada = apertura de t+2 (= cierre de t+1 = 100); salida = cierre de t+6 = 102 → acierto.
    assert tr.iloc[0]["resultado"] == 1 and tr.iloc[0]["pnl"] == 0.85
