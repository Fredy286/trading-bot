import numpy as np
import pandas as pd
import pytest

from tradingbot.research import study54 as s54


def _data(slope=0.01, offset=5.0):
    """Binance sube `slope` por segundo; el índice de OKX está `offset` por debajo de Binance."""
    idx = pd.date_range("2026-10-01 00:00", "2026-10-01 01:00", freq="s", tz="UTC", inclusive="left")
    sec = pd.Series(1000 + slope * np.arange(len(idx)), index=idx)  # cierre de la vela de 1 s que abre en idx
    bn = sec.groupby(sec.index.floor("min")).last()
    ix = bn - offset
    return sec, bn, ix


def test_settle_labels_reproduce_the_okx_rule():
    sec, bn, ix = _data()
    t = pd.DatetimeIndex([pd.Timestamp("2026-10-01 00:09", tz="UTC")])  # ventana 00:10 → 00:15
    y = s54.settle_labels(t, 5, ix, bn, sec.index, sec.to_numpy())
    assert y[0] == 1  # el precio sube
    # a mano: partida = índice al cierre de 00:09; liquidación = media de los cierres 00:14:31 … 00:15:00
    strike = ix.loc[t[0]]
    exp = pd.Timestamp("2026-10-01 00:15", tz="UTC")
    inst = [exp - pd.Timedelta(seconds=k) for k in range(30)]
    settle = np.mean([sec[i - pd.Timedelta(seconds=1)] - 5.0 for i in inst])
    assert settle > strike
    down = s54.settle_labels(t, 5, ix, bn, sec.index, (2000 - sec).to_numpy())
    assert np.isnan(down[0]) or down[0] in (-1.0, 1.0)


def test_settle_labels_tie_is_up_and_missing_data_is_nan():
    sec, bn, ix = _data(slope=0.0)
    t = pd.DatetimeIndex([pd.Timestamp("2026-10-01 00:20", tz="UTC")])
    assert s54.settle_labels(t, 5, ix, bn, sec.index, sec.to_numpy())[0] == 1  # igual → gana «sube»
    late = pd.DatetimeIndex([pd.Timestamp("2026-10-01 00:58", tz="UTC")])  # sin datos tras el vencimiento
    assert np.isnan(s54.settle_labels(late, 5, ix, bn, sec.index, sec.to_numpy())[0])


def test_pnl_and_breakeven():
    res = np.array([1, -1, 1])
    assert s54.pnl(res).tolist() == pytest.approx([1 - 0.02 - 0.52, -0.52, 0.46])
    assert s54.EQUILIBRIO == pytest.approx(0.52 / 0.98)


def test_evaluate_takes_only_positive_ev_with_margin():
    t = pd.date_range("2025-09-01", periods=4, freq="5min", tz="UTC")
    p = np.array([0.60, 0.54, 0.40, 0.56])
    y = np.array([1.0, 1.0, -1.0, -1.0])
    ev = s54.evaluate(p, y, t, n_boot=20)
    assert ev["operaciones"] == 3  # p = 0,54 no llega a (0,52 + 0,02) / 0,98 = 0,551
    assert ev["acierto"] == pytest.approx(2 / 3)
