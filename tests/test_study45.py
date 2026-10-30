"""Estudio 45: estados de entrada/salida, costos al cambiar de posición y semestres anclados al final."""

import numpy as np
import pandas as pd
import pytest

from tradingbot.research.study45 import _state, net_returns, rsi, windows


def test_state_enters_and_leaves_on_events():
    enter = np.array([0, 1, 0, 0, 1, 0], bool)
    leave = np.array([0, 0, 0, 1, 1, 0], bool)
    # la salida solo cuenta estando dentro; fuera, una entrada entra aunque haya salida en la misma vela
    # (con RSI 30/70 y Bollinger nunca coinciden)
    assert list(_state(enter, leave)) == [0, 1, 1, 0, 1, 1]


def test_net_returns_use_the_previous_position_and_charge_each_change():
    t = pd.date_range("2026-01-01", periods=4, freq="4h", tz="UTC")
    b = pd.DataFrame({"c": [100.0, 110.0, 121.0, 121.0]}, index=t)
    pos = pd.DataFrame({"x": [1.0, 1.0, 0.0, 0.0]}, index=t)
    net = net_returns(b, pos, cost=0.01)["x"]
    # vela 1: comprado desde el cierre 0 (+10 %) menos la compra; vela 2: +10 %; vela 3: fuera, menos la venta
    assert net.iloc[1] == pytest.approx(0.10 - 0.01) and net.iloc[2] == pytest.approx(0.10)
    assert net.iloc[3] == pytest.approx(-0.01)
    assert net_returns(b, pos, cost=0.01, lev=2.0)["x"].iloc[1] == pytest.approx(0.20 - 0.02)


def test_rsi_is_high_after_gains_and_windows_end_on_the_last_day():
    c = pd.Series(np.r_[np.linspace(100, 200, 50), np.linspace(200, 100, 50)])
    r = rsi(c)
    assert r.iloc[49] > 90 and r.iloc[99] < 10
    w = windows()
    assert w[-1][1] == pd.Timestamp("2026-10-26", tz="UTC") and w[-1][0] == pd.Timestamp("2026-04-26", tz="UTC")
    assert all(w[i][1] == w[i + 1][0] for i in range(len(w) - 1)) and w[0][0] >= pd.Timestamp("2021-01-01", tz="UTC")
