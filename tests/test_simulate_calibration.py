import numpy as np
import pandas as pd

from tradingbot.research.calibration import Calibrator
from tradingbot.research.contracts import BinaryContract
from tradingbot.research.simulate import ExecParams, max_age_for_horizon, simulate


def _labels(n, dirs):
    return pd.DataFrame({"dir": dirs, "long_px": np.zeros(n), "short_px": np.zeros(n), "entry": np.ones(n),
                         "spread_in": np.zeros(n)})


def test_expired_and_disconnected_signals_are_not_executed():
    n = 1000
    side = np.ones(n)
    lab = {1: _labels(n, np.ones(n)), 2: _labels(n, np.ones(n))}
    # Latencia mediana 30 s con vigencia 20 s → la mayoría caduca.
    sim = simulate(side, np.ones(n, bool), np.zeros(n, bool), lab, BinaryContract(),
                   ExecParams(latency_median_s=30, max_age_s=20, p_disconnect=0.0))
    assert (sim["status"] == 3).mean() > 0.7
    assert np.isnan(sim["pnl"][sim["status"] == 3]).all()
    sim = simulate(side, np.ones(n, bool), np.zeros(n, bool), lab, BinaryContract(),
                   ExecParams(latency_median_s=1, max_age_s=20, p_disconnect=0.5))
    assert 0.4 < (sim["status"] == 4).mean() < 0.6
    assert np.allclose(sim["pnl"][sim["status"] == 0], 0.85)


def test_news_filter_and_no_signal_and_unevaluable():
    n = 6
    side = np.array([1, 1, 0, 1, -1, 1], float)
    want = np.array([1, 1, 1, 0, 1, 1], bool)
    news = np.array([0, 1, 0, 0, 0, 0], bool)
    dirs = np.array([1, 1, 1, 1, 1, np.nan])
    sim = simulate(side, want, news, {1: _labels(n, dirs)}, BinaryContract(),
                   ExecParams(latency_median_s=1, latency_sigma=0.01, max_age_s=20, p_disconnect=0))
    assert sim["status"].tolist() == [0, 2, 1, 1, 0, 5]
    assert sim["pnl"][0] == 0.85 and sim["pnl"][4] == -1.0


def test_max_age_scales_with_horizon():
    assert max_age_for_horizon(1) == 20
    assert max_age_for_horizon(60) == 1200


def test_calibrator_recovers_probabilities_and_intervals():
    rng = np.random.default_rng(0)
    raw = rng.uniform(0, 1, 50_000)
    true_p = 0.4 + 0.2 * raw  # el modelo está mal calibrado: la probabilidad real es más moderada
    y = (rng.random(len(raw)) < true_p).astype(int)
    cal = Calibrator().fit(raw, y)
    p = cal.transform(np.array([0.0, 0.5, 1.0]))
    assert abs(p[0] - 0.4) < 0.05 and abs(p[1] - 0.5) < 0.05 and abs(p[2] - 0.6) < 0.05
    lo, hi, n = cal.interval(np.array([0.58]))
    assert lo[0] < 0.58 < hi[0] and n[0] > 1000
