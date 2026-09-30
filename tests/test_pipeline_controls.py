"""Controles del pipeline completo con datos SINTÉTICOS.

- Control negativo (paseo aleatorio): no debe haber candidatas y el acierto debe rondar 50 %.
- Control positivo (autocorrelación sembrada): el pipeline debe detectar la ventaja en binaria
  y, aun así, rechazar el contado cuando los costos superan el movimiento.
"""

from pathlib import Path

import numpy as np
import pytest

from tradingbot.data import synthetic
from tradingbot.research import report
from tradingbot.research.experiment import load_config, run_symbol

CFG_PATH = Path(__file__).resolve().parents[1] / "config" / "research_demo.toml"


@pytest.fixture(scope="module")
def cfg():
    c = load_config(CFG_PATH)
    c["study"]["horizons"] = [1]
    return c


def _run(phi, cfg):
    raw = synthetic.generate(start="2023-01-02", days=200, phi=phi, seed=11)
    res = run_symbol("SYNTH", raw, "dev", cfg, n_boot=200, log=lambda *a, **k: None)
    df = report.evaluations_frame([res])
    return res, report.select_candidates(df, cfg["acceptance"])


def test_negative_control_yields_no_signal(cfg):
    res, cands = _run(0.0, cfg)
    assert not cands["candidate"].any()
    a = cands[(cands.contract == "binaria") & (cands.policy == "A") & (cands.model == "logit")].iloc[0]
    assert 0.48 < a.hit < 0.52
    # Nunca debe aparecer ≥ 80 % con n suficiente en datos sin señal.
    acc = report.accuracy_target_table([res], 0.80, 100)
    assert not acc["reaches_target"].any()


def test_zero_spread_source_still_produces_decisions(cfg):
    """Regresión: con spread 0 (Binance) spread_rel era NaN y se descartaban TODAS las decisiones."""
    raw = synthetic.generate(start="2023-01-02", days=200, phi=0.0, seed=5)
    for k in ("o", "h", "l", "c"):
        mid = (raw[f"bid_{k}"] + raw[f"ask_{k}"]) / 2
        raw[f"bid_{k}"] = mid
        raw[f"ask_{k}"] = mid
    res = run_symbol("SYNTH", raw, "dev", cfg, n_boot=50, log=lambda *a, **k: None)
    h1 = res["horizons"]["1"]
    assert h1["n_decisions_test"] > 10_000
    assert len(h1["evaluations"]) > 0


def test_positive_control_is_detected(cfg):
    res, cands = _run(-0.3, cfg)
    b = cands[(cands.contract == "binaria") & (cands.model == "logit") & (cands.policy == "B")].iloc[0]
    assert b.hit_lo95 > b.breakeven and b.ev_lo95 > 0 and b.p_holm < 0.05
    assert cands[(cands.contract == "binaria") & cands.candidate].shape[0] >= 1
    spot = cands[(cands.contract == "contado") & cands.candidate]
    assert spot.empty  # el costo supera al movimiento medio a 1 minuto
    assert res["horizons"]["1"]["descriptive"]["spot_breakeven"] > 1.0
    assert np.isfinite(res["horizons"]["1"]["calibration"]["logit"]["ece"])


def test_holdout_verdict_mechanics():
    import pandas as pd

    frozen = {"candidates": [
        {"symbol": "X", "horizon": 15, "contract": "binaria", "model": "logit", "policy": "B"},
        {"symbol": "X", "horizon": 1, "contract": "binaria", "model": "gbm", "policy": "B"},
        {"symbol": "Y", "horizon": 60, "contract": "binaria", "model": "logit", "policy": "B"}]}
    hold = pd.DataFrame([
        dict(symbol="X", horizon=15, contract="binaria", model="logit", policy="B", n_trades=5000, hit=0.58,
             hit_lo95=0.566, breakeven=0.5405, ev=0.07, ev_lo95=0.04, ev_hi95=0.10, pvalue=1e-8),
        dict(symbol="X", horizon=1, contract="binaria", model="gbm", policy="B", n_trades=5000, hit=0.545,
             hit_lo95=0.531, breakeven=0.5405, ev=0.008, ev_lo95=-0.02, ev_hi95=0.03, pvalue=0.2)])
    v = report.holdout_verdict(frozen, hold, None)
    assert [p["horizon"] for p in v["passed"]] == [15]
    assert {p["horizon"] for p in v["passed_min"]} == {15, 1}
    assert v["details"][2]["found"] is False
    empty = report.holdout_verdict(frozen, hold.iloc[1:], None)
    assert empty["verdict"] == "SIN SEÑAL"
