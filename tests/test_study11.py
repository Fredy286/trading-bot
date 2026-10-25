"""Estudio 11: la regla de la primera vela, vela a vela, con un día construido a mano."""

import numpy as np

from tradingbot.research.study11 import day_trade, simple_orb


def _day():
    """Minutos 9:30–15:59 de Nueva York con precio plano en 100 salvo lo que cada prueba cambie."""
    m = np.arange(570, 960)
    n = len(m)
    o, h, l, c = (np.full(n, 100.0) for _ in range(4))
    h += 0.5
    l -= 0.5  # rango de apertura: ORH = 100,5; ORL = 99,5
    return o, h, l, c, m


def _set(arr, i, v):
    arr[i] = v


def test_bullish_break_with_fvg_then_retest_with_engulfing_enters_3_to_1():
    o, h, l, c, m = _day()
    # Velas 8, 9, 10 (9:38–9:40): la 9 rompe ORH con fuerza y deja hueco entre máx[8] y mín[10].
    o[9], c[9], h[9], l[9] = 100.4, 102.0, 102.1, 100.3
    o[10], c[10], h[10], l[10] = 102.0, 102.5, 102.6, 101.0  # mín[10] = 101 > máx[8] = 100,5 → FVG [100,5; 101]
    for i in range(11, 20):
        o[i], c[i], h[i], l[i] = 102.4, 102.3, 102.5, 102.2
    o[20], c[20], h[20], l[20] = 102.2, 101.2, 102.3, 101.1  # vela bajista que baja hacia el FVG
    o[21], c[21], h[21], l[21] = 101.1, 102.4, 102.5, 100.9  # toca el FVG (100,9 ≤ 101) y envuelve: entrada
    risk = 102.4 - min(100.9, 100.5)
    for i in range(22, 60):
        o[i], c[i], h[i], l[i] = 102.4, 102.4, 102.5, 102.3
    h[60], l[60] = 102.4 + 3 * risk + 0.01, 102.3  # TP (sin tocar el SL en la misma vela)
    r = day_trade(o, h, l, c, m, cost=0.1)
    assert r["lado"] == 1 and r["entrada"] == 102.4 and np.isclose(r["sl"], 100.5)
    assert r["motivo"] == "TP" and np.isclose(r["R"], (3 * risk - 0.1) / risk)


def test_fvg_is_cancelled_by_a_close_beyond_it_and_no_trade_without_retest():
    o, h, l, c, m = _day()
    o[9], c[9], h[9], l[9] = 100.4, 102.0, 102.1, 100.3
    o[10], c[10], h[10], l[10] = 102.0, 102.5, 102.6, 101.0
    for i in range(11, len(m)):
        o[i], c[i], h[i], l[i] = 102.4, 102.3, 102.5, 102.2  # nunca vuelve al FVG
    assert day_trade(o, h, l, c, m, cost=0.1) == {"sin_entrada": True}
    c[15] = 100.0  # cierre por debajo del FVG: se cancela antes del retesteo
    o[20], c[20], h[20], l[20] = 102.2, 101.2, 102.3, 101.1
    o[21], c[21], h[21], l[21] = 101.1, 102.4, 102.5, 100.9
    assert day_trade(o, h, l, c, m, cost=0.1) == {"sin_entrada": True}


def test_no_trade_without_complete_opening_range():
    o, h, l, c, m = _day()
    h[2] = np.nan
    assert day_trade(o, h, l, c, m, cost=0.1) is None


def test_simple_orb_follows_the_first_five_minutes():
    o, h, l, c, m = _day()
    c[4] = 101.0  # primera vela de 5 min alcista
    o[5], c[-1] = 101.0, 103.0
    assert np.isclose(simple_orb(o, c, m, cost=0.0), 2.0 / 101.0 * 1e4)
