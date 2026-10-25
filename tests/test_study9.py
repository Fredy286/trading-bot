"""Estudio 9: velas de marco superior solo cuando ya cerraron; regla y simulación sin solapamiento."""

import numpy as np
import pandas as pd

from tradingbot.research.study9 import closed_candles, last_closed, rule_sides, simulate


def _bars(c, start="2024-01-01"):
    c = np.asarray(c, float)
    idx = pd.date_range(start, periods=len(c), freq="min", tz="UTC")
    o = np.r_[c[0], c[:-1]]
    return pd.DataFrame({"o": o, "h": np.maximum(o, c) + 0.01, "l": np.minimum(o, c) - 0.01, "c": c,
                         "spread_o": 0.0, "spread_c": 0.0}, index=idx)


def test_higher_timeframe_values_appear_only_after_the_candle_closes():
    b = _bars(np.arange(3 * 1440, dtype=float) + 100)
    d = closed_candles(b, "D")
    v = last_closed(b, d, pd.DataFrame({"c": d["c"]}))
    # El cierre del primer día está disponible al cierre de su última vela (23:59 → 00:00), no antes.
    assert np.isnan(v["c"].iloc[1438]) and v["c"].iloc[1439] == b["c"].iloc[1439]
    assert v["c"].iloc[2000] == b["c"].iloc[1439]
    w = closed_candles(b, "W")
    assert w.index[0].dayofweek == 0  # semanas de lunes a domingo (2024-01-01 es lunes)


def test_rule_sells_only_when_daily_and_weekly_rsi_are_overbought_and_4h_turns_down():
    days = 200
    up = np.linspace(100, 400, days * 1440)  # subida larga: RSI diario y semanal altos
    b = _bars(up)
    s = rule_sides(b)
    assert (s["regla"] >= 0).all()  # sin estructura bajista de 4H, ninguna venta
    assert (s["sin_4h"] == -1).sum() > 0  # sobrecompra en diario y semanal: sin 4H habría ventas
    assert np.array_equal(s["al_reves"], -s["regla"])


def test_simulation_has_no_overlap_and_enters_one_minute_later():
    c = np.r_[np.full(20, 100.0), np.full(40, 99.0)]
    b = _bars(c)
    side = np.zeros(len(b), int)
    side[0] = side[10] = side[17] = -1
    tr = simulate(b, side, point=0.01)
    assert len(tr) == 2 and tr["time"].iloc[1] == b.index[17]  # la de t = 10 se solapa (vence en t+16)
    # Entrada en la apertura de t+2 = 100, salida al cierre de t+16 = 100 → empate en la primera.
    assert tr["resultado"].iloc[0] == 0
