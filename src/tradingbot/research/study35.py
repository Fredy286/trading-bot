"""Estudio 35 (pre-registro en docs/01, commit 27f7935): modelo congelado de ETH/USDT con la receta de `train_frozen`
(aviso en el segundo 50, clic a +10 s), entrenado UNA vez con 2025-10-26 → 2026-10-25. Su confirmación (p ≥ 0,60) se
evalúa una sola vez después del 2027-01-18; el registro diario guarda sus señales con los aciertos sellados.
"""

from __future__ import annotations

import hashlib
import json
import pickle
import uuid
from pathlib import Path

import numpy as np
import pandas as pd

from ..live.anticipada import CALIB_FRAC, K, LAT, TRAIN_END, TRAIN_START
from ..timeutil import utcnow
from .calibration import Calibrator
from .experiment import git_sha
from .features import FEATURES, compute_features
from .models import fit_predict_proba
from .study3 import load, spot_bars
from .study16 import label, partial_features

SYMBOL = "ETHUSDT"
MODEL_PATH = Path("config/modelos/ETHUSDT_senal_anticipada_k50.pkl")
REG_PATH = Path("config/senal_anticipada_eth.json")
WORK = Path("data/processed/estudio26") / SYMBOL


def train_frozen_eth(root3: Path = Path("data/raw/estudio3"), work: Path = WORK, out: Path = MODEL_PATH,
                     reg: Path = REG_PATH, log=print) -> dict:
    """Misma receta que `live.anticipada.train_frozen` (BTC), con las velas de ETH ya descargadas en el Estudio 26."""
    if Path(out).exists():
        raise FileExistsError(f"{out} ya existe: el modelo se entrena una sola vez (pre-registro).")
    m1 = pd.concat([pd.read_parquet(f) for f in sorted((Path(work) / "1m").glob("*.parquet"))])
    spot = pd.concat([load(root3, SYMBOL, "spot"), m1])
    spot = spot[~spot.index.duplicated(keep="last")].sort_index()
    bars = spot_bars(spot)
    bars = bars[(bars.index >= TRAIN_START - pd.Timedelta(days=3)) & (bars.index < TRAIN_END)]
    prev = compute_features(bars).shift(1)
    tab = pd.read_parquet(Path(work) / "tabla.parquet").reindex(bars.index)
    X = pd.concat([prev[FEATURES], partial_features(tab, bars["o"], np.exp(prev["lvol60"]), K)], axis=1)
    y = label(tab, K, LAT)
    known = (bars.index + pd.Timedelta(minutes=3)) <= TRAIN_END  # resultado conocido antes del fin
    ok = (bars.index >= TRAIN_START) & known & X.notna().all(axis=1).to_numpy() & ~np.isnan(y)
    rows = np.flatnonzero(ok)
    cut = bars.index[rows[int(len(rows) * (1 - CALIB_FRAC))]].floor("D")
    fit = ok & (bars.index < cut - pd.Timedelta(minutes=3)) & (y != 0)  # purga entre ajuste y calibración
    cal = ok & (bars.index >= cut) & (y != 0)
    model, (pc,) = fit_predict_proba("gbm", X[fit], (y[fit] == 1).astype(int), [X[cal]], seed=2024,
                                     features=list(X.columns))
    calib = Calibrator().fit(pc, (y[cal] == 1).astype(int))
    q = float(np.mean(y[ok & (bars.index >= cut)] == 0))
    bundle = {"model": model, "calibrator": calib, "features": list(X.columns), "k": K, "latencia": LAT, "q": q,
              "train_start": str(TRAIN_START), "train_end": str(TRAIN_END), "calib_desde": str(cut),
              "n_ajuste": int(fit.sum()), "n_calibracion": int(cal.sum()), "payout": 0.85, "ev_margin": 0.02,
              "umbral": 0.60, "symbol": SYMBOL,
              "model_id": f"{SYMBOL}-anticipada-k{K}-L{LAT}-{uuid.uuid4().hex[:6]}"}
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    with open(out, "wb") as fh:
        pickle.dump(bundle, fh)
    sha = hashlib.sha256(Path(out).read_bytes()).hexdigest()
    meta = {k: v for k, v in bundle.items() if k not in ("model", "calibrator")}
    meta.update({"model_file": str(out), "model_sha256": sha, "git_sha": git_sha(), "creado": utcnow().isoformat(),
                 "registro": "Estudio 35 (pre-registro 27f7935): modelo congelado de ETH para la confirmación"})
    Path(reg).write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    log(f"Modelo {bundle['model_id']}: ajuste={fit.sum():,} calibración={cal.sum():,} q={q:.4f} sha256={sha[:12]}…")
    return meta
