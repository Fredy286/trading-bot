"""Estudio 6: las variables de zonas son causales y siguen las definiciones del pre-registro."""

import numpy as np
import pandas as pd

from tradingbot.research.study6 import ZONE_FEATURES, zone_features


def _bars(n=3 * 1440, seed=0, base=1.1000, sd=2e-4):
    idx = pd.date_range("2024-01-01", periods=n, freq="min", tz="UTC")
    rng = np.random.default_rng(seed)
    c = base * np.exp(np.cumsum(rng.normal(0, sd, n)))
    o = np.r_[base, c[:-1]]
    h = np.maximum(o, c) * (1 + rng.uniform(0, sd, n))
    l = np.minimum(o, c) * (1 - rng.uniform(0, sd, n))
    return pd.DataFrame({"o": o, "h": h, "l": l, "c": c}, index=idx)


def test_zone_features_follow_the_registered_definitions():
    b = _bars()
    step = 0.0100
    f = zone_features(b, step)
    assert list(f.columns) == ZONE_FEATURES
    t = 2 * 1440 + 500  # tercer día: el anterior está completo
    c, h, l = b["c"], b["h"], b["l"]
    lr = np.log(c).diff()
    sig = lr.iloc[t - 59:t + 1].std() * np.sqrt(15)
    r = round(c.iloc[t] / step) * step
    assert np.isclose(f["z_rn"].iloc[t], (np.log(c.iloc[t]) - np.log(r)) / sig)
    prev = b.iloc[1440:2880]
    assert np.isclose(f["z_pdh"].iloc[t], (np.log(c.iloc[t]) - np.log(prev["h"].max())) / sig)
    assert np.isclose(f["z_pdl"].iloc[t], (np.log(c.iloc[t]) - np.log(prev["l"].min())) / sig)
    w = b.iloc[t - 239:t - 14]  # velas t−239 … t−15
    hi, lo = w["h"].max(), w["l"].min()
    assert len(w) == 225 and np.isclose(f["z_hi240"].iloc[t], (np.log(c.iloc[t]) - np.log(hi)) / sig)
    assert f["z_t_hi"].iloc[t] == np.sum(np.log(hi) - np.log(w["h"]) <= 0.25 * sig) >= 1
    assert f["z_t_lo"].iloc[t] == np.sum(np.log(w["l"]) - np.log(lo) <= 0.25 * sig) >= 1
    w15 = b.iloc[t - 14:t + 1]
    assert np.isclose(f["z_rej15"].iloc[t], (c.iloc[t] - w15["l"].min()) / (w15["h"].max() - w15["l"].min()))
    # Primer día: sin día anterior completo → NaN.
    assert f["z_pdh"].iloc[:1440].isna().all() and f["z_pdh"].iloc[1440 + 300:].notna().all()


def test_round_number_cross_and_touch():
    idx = pd.date_range("2024-01-01", periods=40, freq="min", tz="UTC")
    c = np.full(40, 1.0950)
    c[20:] = 1.1050  # cruza 1,1000 hacia arriba en la vela 20
    b = pd.DataFrame({"o": c, "h": c, "l": c, "c": c}, index=idx)
    b.iloc[20, b.columns.get_loc("l")] = 1.0950  # la vela del cruce toca 1,1000
    b.iloc[10, b.columns.get_loc("h")] = 1.1000  # toque exacto (sin errores de redondeo)
    f = zone_features(b, 0.0100)
    assert (f["z_rn_x15"].iloc[20:35] == 1).all() and f["z_rn_x15"].iloc[35] == 0
    assert f["z_rn_n"].iloc[10] == 0 and f["z_rn_n"].iloc[15] == 5 and f["z_rn_n"].iloc[25] == 5
    assert f["z_rn_n"].iloc[5] == 240  # sin toque previo: tope


def test_zone_features_are_causal():
    b = _bars(seed=1)
    t = 2 * 1440 + 777
    f = zone_features(b, 0.0100)
    b2 = b.copy()
    b2.iloc[t + 1:] *= 1.07
    f2 = zone_features(b2, 0.0100)
    pd.testing.assert_series_equal(f.iloc[t], f2.iloc[t])


def test_touch_counts_only_on_requested_rows_match_full_computation():
    b = _bars(seed=2)
    rows = np.arange(300, len(b), 15)
    full, part = zone_features(b, 0.0100), zone_features(b, 0.0100, rows=rows)
    pd.testing.assert_frame_equal(full.iloc[rows], part.iloc[rows])
