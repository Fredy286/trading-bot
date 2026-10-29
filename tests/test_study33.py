"""Estudio 33: variables de reloj del minuto que se opera y ejecución completa con datos sintéticos."""

import json

import numpy as np
import pandas as pd

from tradingbot.research import study33


def test_clock_features_describe_the_traded_minute():
    idx = pd.DatetimeIndex(["2025-01-01 07:59", "2025-01-01 08:00", "2025-01-01 08:04", "2025-01-01 08:09",
                            "2025-01-01 08:14", "2025-01-01 15:58"], tz="UTC")
    f = study33.clock_features(idx)
    # Decisión al cierre de t: se opera la vela que abre en t + 1 (08:00, 08:01, 08:05, 08:10, 08:15, 15:59).
    assert f["k_q15"].tolist() == [1, 0, 0, 0, 1, 0]
    assert f["k_hora0"].tolist() == [1, 0, 0, 0, 0, 0]
    assert f["k_m5"].tolist() == [0, 0, 1, 1, 0, 0]
    assert f["k_fund0"].tolist() == [1, 0, 0, 0, 0, 0]
    assert f["k_fund_post"].tolist() == [0, 1, 1, 0, 0, 0]
    assert np.allclose(f["k_fund_min"], [0, 479 / 480, 475 / 480, 470 / 480, 465 / 480, 1 / 480])
    assert np.allclose(f.loc[idx[0], ["k_ph15_sin", "k_ph15_cos"]], [0, 1])
    assert list(f.columns) == study33.CLOCK


def test_run_end_to_end_on_synthetic_bars(tmp_path, monkeypatch):
    rng = np.random.default_rng(1)
    idx = pd.date_range("2024-01-01", "2024-04-01", freq="min", tz="UTC", inclusive="left")
    c = 40000 * np.exp(np.cumsum(rng.normal(0, 4e-4, len(idx))))
    o = np.r_[c[0], c[:-1]]
    df = pd.DataFrame({"o": o, "h": np.maximum(o, c) * 1.0002, "l": np.minimum(o, c) * 0.9998, "c": c,
                       "volume": rng.uniform(1, 5, len(idx)), "trades": 100.0, "taker_buy_base": 1.0},
                      index=pd.DatetimeIndex(idx, name="time"))
    root = tmp_path / "raw"
    (root / "BTCUSDT" / "spot").mkdir(parents=True)
    df.to_parquet(root / "BTCUSDT" / "spot" / "2024.parquet")
    real = study33.load_config

    def small(path):
        cfg = real(path)
        cfg["study"] = {**cfg["study"], "train_months": 1, "step_months": 1, "max_fit_rows": 20000}
        return cfg

    monkeypatch.setattr(study33, "load_config", small)
    monkeypatch.setattr(study33, "DATA_START", "2024-01-01")
    monkeypatch.setattr(study33, "DATA_END", "2024-04-01")
    monkeypatch.setattr(study33, "PERIODS", {"desarrollo": ("2024-02-01", "2024-03-01"),
                                             "verificacion": ("2024-03-01", "2024-04-01")})
    rep = study33.run(root, tmp_path / "out", n_boot=20, log=lambda *a: None, download=False)
    assert set(rep["criterios"]) == {"dev_logloss_ic", "dev_ev", "verif_logloss", "verif_ev"}
    assert rep["desarrollo"]["minutos"] > 30000
    saved = json.loads((tmp_path / "out" / "resultado.json").read_text(encoding="utf-8"))
    assert saved["variables"] == study33.CLOCK
