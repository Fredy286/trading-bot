"""Estudio 48: racha reciente sin mirar el futuro, bootstrap de la diferencia y ejecución con datos sintéticos."""

import json

import numpy as np
import pandas as pd

from tradingbot.research import study48


def _trades(n, start="2024-01-01"):
    t = pd.date_range(start, periods=n, freq="min", tz="UTC")
    return t, t + pd.Timedelta(minutes=2)


def test_streak_uses_only_resolved_trades(monkeypatch):
    monkeypatch.setattr(study48, "N_LAST", 3)
    monkeypatch.setattr(study48, "MIN_DAYS_N", 2)
    t, le = _trades(8)
    res = np.array([1, 1, -1, 0, 1, -1, -1, 1], float)
    a, b = study48.streak_rates(t, le, res)
    # En t[i] están resueltas las operaciones con label_end ≤ t[i], es decir, las de índice ≤ i − 2 (sin empates).
    # En t[i] están resueltas las de índice ≤ i − 2. En t[3] solo hay 2 → sin definir.
    assert np.isnan(a[:4]).all()
    assert np.isclose(a[4], 2 / 3)  # resueltas 0, 1, 2 → [1, 1, −1]
    # t[7]: resueltas 0..5 sin el empate (índice 3) → últimas 3 decididas = [−1, 1, −1] → 1/3
    assert np.isclose(a[7], 1 / 3)
    # 7 días: todas las resueltas. t[7]: 0..5 sin empate → [1,1,−1,1,−1] → 3/5
    assert np.isclose(b[7], 3 / 5)


def test_streak_ignores_future_outcomes():
    t, le = _trades(700)
    rng = np.random.default_rng(0)
    res = rng.choice([-1.0, 1.0], len(t))
    a1, b1 = study48.streak_rates(t, le, res)
    res2 = res.copy()
    res2[600:] = 1.0  # cambiar el futuro no puede cambiar la racha del pasado
    a2, b2 = study48.streak_rates(t, le, res2)
    assert np.allclose(a1[:602], a2[:602], equal_nan=True)
    assert np.allclose(b1[:602], b2[:602], equal_nan=True)
    assert not np.allclose(a1[603:], a2[603:], equal_nan=True)


def test_diff_bootstrap_detects_and_rejects():
    rng = np.random.default_rng(3)
    n = 20000
    weeks = np.repeat(np.arange(40), n // 40)
    taken = rng.random(n) < 0.5
    res = np.where(rng.random(n) < np.where(taken, 0.6, 0.5), 1.0, -1.0)
    d = study48.diff_bootstrap(res, taken, weeks, 300)
    assert d["lo"] > 0.05 and abs(d["diferencia"] - 0.1) < 0.03
    res0 = np.where(rng.random(n) < 0.55, 1.0, -1.0)
    d0 = study48.diff_bootstrap(res0, taken, weeks, 300)
    assert d0["lo"] < 0 < d0["hi"]


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
    real = study48.load_config

    def small(path):
        cfg = real(path)
        cfg["study"] = {**cfg["study"], "train_months": 1, "step_months": 1, "max_fit_rows": 20000}
        cfg["contracts"] = {**cfg["contracts"], "binary_ev_margin": -1.0}  # que opere siempre (datos al azar)
        return cfg

    monkeypatch.setattr(study48, "load_config", small)
    monkeypatch.setattr(study48, "DATA_START", "2024-01-01")
    monkeypatch.setattr(study48, "DATA_END", "2024-04-01")
    monkeypatch.setattr(study48, "PERIODS", {"desarrollo": ("2024-02-01", "2024-03-01"),
                                             "verificacion": ("2024-03-01", "2024-04-01")})
    rep = study48.run(root, tmp_path / "out", n_boot=20, log=lambda *a: None, download=False)
    for h in ("H48a", "H48b"):
        assert set(rep["hipotesis"][h]["criterios"]) == {"dev_diferencia_ic", "dev_ev", "verif_acierto", "verif_ev",
                                                         "min_300"}
        dev = rep["hipotesis"][h]["desarrollo"]
        assert dev["muestra_comun"] == dev["tomadas"]["operaciones"] + dev["saltadas"]["operaciones"]
        assert dev["muestra_comun"] > 20000
    saved = json.loads((tmp_path / "out" / "resultado.json").read_text(encoding="utf-8"))
    assert saved["equilibrio"] == 1 / 1.85
