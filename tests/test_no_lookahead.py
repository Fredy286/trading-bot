"""Prueba central contra el sesgo de anticipación: alterar el futuro no debe cambiar el pasado."""

import numpy as np
import pandas as pd

from tradingbot.research.features import compute_features, rolling_abs_move
from tradingbot.research.labels import make_labels


def _perturb_after(bars: pd.DataFrame, cut: pd.Timestamp, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    b = bars.copy()
    m = b.index > cut
    k = int(m.sum())
    factor = 1 + rng.normal(0, 0.01, k)
    for col in ("o", "h", "l", "c"):
        b.loc[m, col] = b.loc[m, col] * factor
    b.loc[m, "spread_o"] = b.loc[m, "spread_o"] * 3
    b.loc[m, "spread_c"] = b.loc[m, "spread_c"] * 3
    b.loc[m, "volume"] = b.loc[m, "volume"] * 10
    b.loc[m, "no_tick"] = ~b.loc[m, "no_tick"].astype(bool)
    return b


def test_features_do_not_use_future(synth_bars):
    bars = synth_bars
    valid_times = bars.index[bars["c"].notna()]
    cut = valid_times[len(valid_times) // 2]
    f0 = compute_features(bars)
    f1 = compute_features(_perturb_after(bars, cut))
    past = f0.index <= cut
    a, b = f0[past].to_numpy(), f1[past].to_numpy()
    assert np.array_equal(np.isnan(a), np.isnan(b))
    assert np.allclose(a[~np.isnan(a)], b[~np.isnan(b)])
    # Y el futuro sí cambia (la perturbación fue efectiva).
    assert not np.allclose(np.nan_to_num(f0[~past].to_numpy()), np.nan_to_num(f1[~past].to_numpy()))


def test_abs_move_estimate_is_causal(synth_bars):
    cut = synth_bars.index[len(synth_bars) // 2]
    m0 = rolling_abs_move(synth_bars, 5)
    m1 = rolling_abs_move(_perturb_after(synth_bars, cut), 5)
    past = m0.index <= cut
    assert np.allclose(m0[past].fillna(-1), m1[past].fillna(-1))


def test_labels_only_depend_on_their_window(synth_bars):
    h, d = 5, 1
    cut = synth_bars.index[len(synth_bars) // 2]
    l0 = make_labels(synth_bars, h, d, 1e-5)
    l1 = make_labels(_perturb_after(synth_bars, cut), h, d, 1e-5)
    # Las etiquetas cuya ventana termina antes del corte no cambian.
    safe = l0.index <= cut - pd.Timedelta(minutes=h + d)
    assert np.allclose(l0.loc[safe, "move"].fillna(9), l1.loc[safe, "move"].fillna(9))
