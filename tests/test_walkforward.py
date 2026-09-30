import numpy as np
import pandas as pd
import pytest

from tradingbot.research.walkforward import enforce_lock, make_folds, stage_folds

CFG = {"dev_test_start": "2022-01-01", "holdout_start": "2025-09-01", "holdout_end": "2026-09-01",
       "step_months": 3, "train_months": 12, "calib_frac": 0.2}


def test_folds_are_chronological_and_cover_dev():
    folds = stage_folds("dev", CFG)
    assert folds[0].test_start == pd.Timestamp("2022-01-01", tz="UTC")
    assert folds[-1].test_end == pd.Timestamp("2025-09-01", tz="UTC")
    for f in folds:
        assert f.train_start < f.calib_start < f.test_start < f.test_end
    for a, b in zip(folds, folds[1:]):
        assert a.test_end == b.test_start
    hold = stage_folds("holdout", CFG)
    assert hold[0].test_start == pd.Timestamp("2025-09-01", tz="UTC")
    assert all(f.test_start >= pd.Timestamp("2025-09-01", tz="UTC") for f in hold)


def test_purge_prevents_label_overlap():
    f = make_folds("2023-01-01", "2023-04-01", 3, 2, 0.25)[0]
    times = pd.date_range("2022-10-15", "2023-04-10", freq="h", tz="UTC")
    label_end = times + pd.Timedelta(hours=5)  # etiquetas de 5 horas
    fit, cal, test = f.masks(times, label_end)
    assert not (fit & cal).any() and not (cal & test).any() and not (fit & test).any()
    le = pd.DatetimeIndex(label_end)
    assert (le[fit] <= f.calib_start).all()
    assert (le[cal] <= f.test_start).all()
    # Las muestras cuya etiqueta cruza el límite quedan fuera de ambos tramos.
    boundary = (times < f.calib_start) & (le > f.calib_start)
    assert boundary.sum() > 0 and not (fit[boundary]).any() and not (cal[boundary]).any()


def test_dev_stage_drops_holdout_data():
    idx = pd.date_range("2025-08-31 23:50", "2025-09-01 00:10", freq="min", tz="UTC")
    bars = pd.DataFrame({"c": np.arange(len(idx), dtype=float)}, index=idx)
    dev = enforce_lock(bars, "dev", CFG)
    assert dev.index.max() < pd.Timestamp("2025-09-01", tz="UTC")
    assert len(enforce_lock(bars, "holdout", CFG)) == len(bars)


def test_unknown_stage_rejected():
    with pytest.raises(ValueError):
        stage_folds("final", CFG)
