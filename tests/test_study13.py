"""Estudio 13: el selector elige, minuto a minuto, la moneda con mayor EV estimado que supere el margen."""

import json

import numpy as np
import pandas as pd

from tradingbot.research import study13


def test_selector_picks_the_highest_ev_coin_each_minute(tmp_path, monkeypatch):
    idx = pd.date_range("2024-01-01", periods=6, freq="min", tz="UTC")
    work = tmp_path / "work"
    work.mkdir()
    rng = np.random.default_rng(0)
    for k, s in enumerate(study13.UNIVERSE):
        ev = np.full(6, -0.1, dtype=np.float32)
        if s == "BTCUSDT":
            ev[:] = [0.05, 0.03, -0.1, 0.03, -0.1, -0.1]
        if s == "SOLUSDT":
            ev[:] = [0.04, 0.06, 0.03, -0.1, -0.1, -0.1]
        side = np.ones(6, dtype=np.int8)
        dirs = np.ones(6, dtype=np.int8) if s != "SOLUSDT" else np.array([1, -1, 1, 1, 1, 1], dtype=np.int8)
        pd.DataFrame({"ev": ev, "lado": side, "dir": dirs}, index=idx).to_parquet(work / f"{s}.parquet")
    rep = study13.run(out_dir=tmp_path / "out", work=work, n_boot=20, log=lambda *a: None)
    sel = rep["selector"]
    # Minuto 0 → BTC (0,05 > 0,04); 1 → SOL (0,06); 2 → SOL (0,03); 3 → BTC; 4 y 5: nadie supera 0,02.
    assert sel["operaciones"] == 4 and sel["elecciones_por_moneda"] == {"BTCUSDT": 2, "SOLUSDT": 2}
    assert sel["aciertos"] == 3  # la elección de SOL en el minuto 1 falla
    assert rep["cada_moneda_sola"]["BTCUSDT"]["operaciones"] == 3
    assert json.loads((tmp_path / "out" / "dev.json").read_text(encoding="utf-8"))["universo"][0] == "BTCUSDT"
