import numpy as np
import pandas as pd

from tradingbot.research.labels import decision_mask, make_labels
from tests.conftest import make_bars


def test_direction_entry_exit_and_ties():
    closes = [1.10000, 1.10010, 1.10005, 1.10005, 1.10020, 1.10020]
    bars = make_bars(closes)
    lab = make_labels(bars, horizon=1, entry_delay=1, point=1e-5)
    # Decisión en t=0: entrada = apertura t+1 = 1.10000, salida = cierre t+1 = 1.10010 → sube.
    assert lab["entry"].iloc[0] == 1.10000
    assert lab["exit"].iloc[0] == 1.10010
    assert lab["dir"].iloc[0] == 1
    # t=1: 1.10010 → 1.10005 baja.
    assert lab["dir"].iloc[1] == -1
    # t=2: 1.10005 → 1.10005 empate.
    assert lab["dir"].iloc[2] == 0
    # Última fila: no hay futuro → no evaluable.
    assert np.isnan(lab["dir"].iloc[-1])


def test_missing_bar_inside_window_is_unevaluable():
    bars = make_bars([1.0, 1.1, 1.2, 1.3, 1.4, 1.5])
    bars.iloc[3, bars.columns.get_loc("c")] = np.nan  # falta el cierre de la vela 3
    lab = make_labels(bars, horizon=3, entry_delay=1, point=1e-5)
    # t=0 usa velas 1..3 → falta la 3 → NaN.
    assert np.isnan(lab["dir"].iloc[0])
    # t=1 usa velas 2..4 → incluye la 3 → NaN.
    assert np.isnan(lab["dir"].iloc[1])


def test_spot_pnl_pays_full_spread():
    bars = make_bars([1.0, 1.0, 1.0], spread=0.0002)
    lab = make_labels(bars, horizon=1, entry_delay=1, point=1e-5)
    # Precio sin cambio: largo y corto pierden exactamente el spread (mitad a la entrada y mitad a la salida).
    assert np.isclose(lab["long_px"].iloc[0], -0.0002)
    assert np.isclose(lab["short_px"].iloc[0], -0.0002)


def test_entry_delay_two_shifts_entry():
    bars = make_bars([1.0, 1.1, 1.2, 1.3])
    lab = make_labels(bars, horizon=1, entry_delay=2, point=1e-5)
    assert lab["entry"].iloc[0] == bars["o"].iloc[2]
    assert lab["exit"].iloc[0] == bars["c"].iloc[2]
    assert lab["label_end"].iloc[0] == bars.index[0] + pd.Timedelta(minutes=3)


def test_decision_mask_non_overlapping():
    idx = pd.date_range("2024-01-01", periods=60, freq="min", tz="UTC")
    m = decision_mask(idx, 15)
    assert m.sum() == 4 and m[0] and m[15] and not m[1]
    assert decision_mask(idx, 1).all()
