"""Estudio 47: lectura de los archivos diarios de Gate y precio reconstruido de IQ Option con pesos."""

import gzip

import pandas as pd
import pytest

from tradingbot.research.study47 import WEIGHTS, iq_price, parse_gate


def test_parse_gate_reads_time_and_close():
    raw = gzip.compress(b"1788220800,0.75,78555.4,78583.2,78555.4,78583.2\n1788220860,0.73,78582.9,78583.0,78555.4,78555.4\n")
    s = parse_gate(raw)
    assert list(s) == [78555.4, 78582.9]
    assert s.index[0] == pd.Timestamp(1788220800, unit="s", tz="UTC")


def test_iq_price_is_the_weighted_mean_and_needs_every_venue():
    t = pd.date_range("2026-01-01", periods=2, freq="min", tz="UTC")
    closes = {"binance": pd.Series([100.0, 100.0], index=t), "bybit": pd.Series([90.0, 90.0], index=t),
              "okx": pd.Series([95.0, 95.0], index=t), "gate": pd.Series([92.0], index=t[:1])}
    p = iq_price(closes)
    expected = (100 * WEIGHTS["binance"] + 90 * WEIGHTS["bybit"] + 95 * WEIGHTS["okx"] + 92 * WEIGHTS["gate"]) / sum(WEIGHTS.values())
    assert len(p) == 1 and p.iloc[0] == pytest.approx(expected)
    assert sum(WEIGHTS.values()) == pytest.approx(1.0)


def test_iq_at_is_exact_at_minute_closes_and_interpolates_the_basis_inside():
    import numpy as np
    from tradingbot.research.study47 import iq_at
    sec_t = pd.date_range("2026-01-01 00:00:00", periods=300, freq="s", tz="UTC")
    sec_c = pd.Series(100.0 + np.arange(300) * 0.1, index=sec_t)  # Binance sube 0,1 por segundo
    basis = pd.Series([1.0, 3.0, 5.0, 7.0], index=pd.date_range("2026-01-01", periods=4, freq="min", tz="UTC"))
    T = pd.DatetimeIndex(["2026-01-01 00:01:00", "2026-01-01 00:01:30"], tz="UTC").to_numpy()
    v = iq_at(T, sec_c.index.to_numpy(), sec_c.to_numpy(), basis)
    # 00:01:00 = cierre del minuto 00:00 → Binance del segundo 59 (105,9) − diferencia del minuto 00:00 (1,0)
    assert v[0] == pytest.approx(105.9 - 1.0)
    # 00:01:30: Binance del segundo 89 (108,9) − diferencia a mitad de camino entre 1,0 y 3,0
    assert v[1] == pytest.approx(108.9 - 2.0)
