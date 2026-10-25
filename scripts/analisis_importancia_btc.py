"""¿Qué datos generan la ventaja del GBM de BTC a 1 minuto? (exploratorio, docs/08).

Entrena el GBM del proyecto con 2024 (80 % ajuste, 20 % calibración) y mide fuera de muestra, en 2025-01 → 2025-08,
cuánto empeora el log-loss al barajar cada grupo de variables (importancia por permutación). Periodo ya usado en
la fase de desarrollo: no decide nada, solo explica de dónde sale la ventaja que ya se validó.

Uso: .venv/bin/python scripts/analisis_importancia_btc.py  → results/analisis/importancia_btc.json
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from tradingbot.instruments import get_instrument
from tradingbot.research.calibration import Calibrator
from tradingbot.research.features import FEATURES, compute_features
from tradingbot.research.labels import make_labels
from tradingbot.research.models import fit_predict_proba
from tradingbot.research.study3 import load, spot_bars

RAIZ = Path(__file__).resolve().parents[1]
GRUPOS = {
    "último minuto (r0)": ["r0"],
    "minutos 2 a 5 (r1–r4)": ["r1", "r2", "r3", "r4"],
    "tendencia 5–240 min (cum)": ["cum5", "cum15", "cum60", "cum240"],
    "volatilidad (niveles y cociente)": ["lvol15", "lvol60", "lvol240", "vol_ratio"],
    "tamaño de la última vela (range)": ["range"],
    "dónde cerró la última vela en su rango (clpos)": ["clpos"],
    "medias, RSI, Bollinger": ["d_sma20", "d_sma60", "rsi14", "boll_z"],
    "volumen, spread, sin operaciones": ["spread_vol", "spread_rel", "vol_rel", "notick60"],
    "hora y día": ["tod_sin", "tod_cos", "dow"],
    "calendario de noticias": ["sched_next"],
}


def _ll(p, y):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return float(-(y * np.log(p) + (1 - y) * np.log(1 - p)).mean())


def main() -> None:
    bars = spot_bars(load(RAIZ / "data/raw/estudio3", "BTCUSDT", "spot"))
    bars = bars[(bars.index >= "2023-12-25") & (bars.index < "2025-09-01")]
    pf = compute_features(bars)
    y = make_labels(bars, 1, 1, get_instrument("BTCUSDT").point)["dir"].to_numpy()
    ok = pf.notna().all(axis=1).to_numpy() & ~np.isnan(y) & (y != 0)
    t = bars.index
    fit = ok & (t >= "2024-01-01") & (t < "2024-10-13")
    cal = ok & (t >= "2024-10-14") & (t < "2024-12-31")
    test = ok & (t >= "2025-01-01")
    yb = (y == 1).astype(int)
    _, (pc, pt) = fit_predict_proba("gbm", pf[fit], yb[fit], [pf[cal], pf[test]], seed=2024)
    calib = Calibrator().fit(pc, yb[cal])
    model, _ = fit_predict_proba("gbm", pf[fit], yb[fit], [pf[cal].iloc[:1]], seed=2024)
    X = pf[test][FEATURES].to_numpy().copy()
    yt = yb[test]
    base = _ll(calib.transform(model.predict_proba(X)[:, 1]), yt)
    acc = float(np.mean((calib.transform(model.predict_proba(X)[:, 1]) >= 0.5) == (yt == 1)))
    rng = np.random.default_rng(20261025)
    out = {"periodo_prueba": "2025-01-01 → 2025-08-31", "decisiones": int(test.sum()), "logloss_base": base,
           "acierto_todas_las_decisiones": acc, "grupos": {}}
    for name, cols in GRUPOS.items():
        idx = [FEATURES.index(c) for c in cols]
        deltas = []
        for _ in range(3):
            Xp = X.copy()
            perm = rng.permutation(len(Xp))
            Xp[:, idx] = Xp[perm][:, idx]  # se barajan juntas las variables del grupo
            deltas.append(_ll(calib.transform(model.predict_proba(Xp)[:, 1]), yt) - base)
        out["grupos"][name] = {"aumento_logloss": float(np.mean(deltas)), "min": float(min(deltas)),
                               "max": float(max(deltas))}
        print(f"{name:38s} +{np.mean(deltas):.6f}", flush=True)
    dest = RAIZ / "results/analisis/importancia_btc.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("decisiones", "logloss_base", "acierto_todas_las_decisiones")}, indent=2))


if __name__ == "__main__":
    main()
