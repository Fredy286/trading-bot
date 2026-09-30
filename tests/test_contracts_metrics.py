import numpy as np
import pytest

from tradingbot.research.contracts import BinaryContract, SpotContract
from tradingbot.research.metrics import (block_bootstrap_mean, holm, max_drawdown, reliability, wilson)


def test_binary_breakeven_table():
    assert BinaryContract(0.85).breakeven() == pytest.approx(0.540540, abs=1e-6)
    assert BinaryContract(0.80).breakeven() == pytest.approx(0.555556, abs=1e-6)
    assert BinaryContract(0.85, "loss").breakeven(0.10) == pytest.approx(0.600601, abs=1e-6)


def test_binary_pnl_and_ev():
    c = BinaryContract(0.85, "refund")
    pnl = c.pnl(np.array([1, 1, -1, -1]), np.array([1, -1, -1, 0]))
    assert pnl.tolist() == [0.85, -1.0, 0.85, 0.0]
    assert BinaryContract(0.85, "loss").pnl(np.array([1]), np.array([0]))[0] == -1.0
    # EV = 0 exactamente en el umbral.
    assert c.ev(np.array([c.breakeven()]), np.array([0.0]))[0] == pytest.approx(0.0, abs=1e-12)
    # 80 % de acierto con pago 85 % → +0,48 (cifra del informe).
    assert c.ev(np.array([0.8]), np.array([0.0]))[0] == pytest.approx(0.48)


def test_spot_pnl_and_breakeven():
    s = SpotContract(commission_px=0.00007)
    entry = np.array([1.1, 1.1])
    pnl = s.pnl_bps(np.array([1, -1]), np.array([0.0001, 0.0001]), np.array([-0.0003, -0.0003]), entry)
    assert pnl[0] == pytest.approx((0.0001 - 0.00007) / 1.1 * 1e4)
    assert pnl[1] == pytest.approx((-0.0003 - 0.00007) / 1.1 * 1e4)
    assert SpotContract.breakeven(1.0, 0.5) == pytest.approx(0.75)
    assert SpotContract.breakeven(0.5, 1.0) > 1.0  # inalcanzable


def test_wilson_known_values():
    lo, hi = wilson(50, 100)
    assert lo == pytest.approx(0.4038, abs=1e-3) and hi == pytest.approx(0.5962, abs=1e-3)
    lo, hi = wilson(0, 0)
    assert np.isnan(lo) and np.isnan(hi)


def test_holm_adjustment():
    adj = holm([0.01, 0.04, 0.03, 0.5])
    assert adj == pytest.approx([0.04, 0.09, 0.09, 0.5])


def test_max_drawdown():
    assert max_drawdown(np.array([1, -2, 1, -3, 5])) == pytest.approx(4.0)
    assert max_drawdown(np.array([])) == 0.0


def test_block_bootstrap_ci_non_degenerate():
    rng = np.random.default_rng(0)
    vals = rng.normal(0.1, 1.0, 5000)
    blocks = np.repeat(np.arange(100), 50)
    r = block_bootstrap_mean(vals, blocks, n_boot=500)
    assert r["lo"] < r["mean"] < r["hi"]
    assert r["hi"] - r["lo"] > 0.01
    null = block_bootstrap_mean(rng.normal(0, 1, 5000), blocks, n_boot=500)
    assert null["p_le_0"] > 0.01


def test_reliability_perfectly_calibrated():
    rng = np.random.default_rng(1)
    p = rng.uniform(0.3, 0.7, 200_000)
    y = (rng.random(len(p)) < p).astype(float)
    tab, ece = reliability(p, y, 10)
    assert ece < 0.01
    assert len(tab) == 10
