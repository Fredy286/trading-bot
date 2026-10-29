"""Estudio 33 (pre-registro en docs/01, commit aea2c8b): ¿las variables de «reloj» (posición del minuto en el cuarto
de hora y distancia a la financiación de los perpetuos) mejoran el GBM de BTC/USDT 1 min de los Estudios 7 y 13?

Walk-forward trimestral (12 meses de entrenamiento) en desarrollo (2022-01 → 2025-08) y verificación
(2025-09 → 2026-09). Las variables se calculan sobre el minuto que se opera (t + 1): solo calendario, sin precios.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from ..instruments import get_instrument
from .calibration import Calibrator
from .contracts import BinaryContract
from .experiment import git_sha, jsonable, load_config
from .features import FEATURES, compute_features
from .labels import make_labels
from .metrics import block_bootstrap_mean
from .models import fit_predict_proba
from .study13 import _stats
from .walkforward import make_folds

SYMBOL = "BTCUSDT"
DATA_START, DATA_END = "2021-01-01", "2026-10-01"  # archivos mensuales hasta 2026-09 (nada posterior al 2026-10-25)
PERIODS = {"desarrollo": ("2022-01-01", "2025-09-01"), "verificacion": ("2025-09-01", "2026-10-01")}
CLOCK = ["k_q15", "k_m5", "k_ph15_sin", "k_ph15_cos", "k_hora0", "k_fund_min", "k_fund0", "k_fund_post"]


def clock_features(index: pd.DatetimeIndex) -> pd.DataFrame:
    """Variables de calendario del minuto que se opera (el que abre en t + 1 min)."""
    nxt = index + pd.Timedelta(minutes=1)
    m = nxt.minute.to_numpy()
    mod = nxt.hour.to_numpy() * 60 + m  # minuto del día UTC
    since_fund = mod % 480  # financiación de Binance a las 00, 08 y 16 UTC
    ph = (m % 15) / 15
    f = pd.DataFrame(index=index)
    f["k_q15"] = (m % 15 == 0).astype(float)
    f["k_m5"] = ((m % 5 == 0) & (m % 15 != 0)).astype(float)
    f["k_ph15_sin"] = np.sin(2 * np.pi * ph)
    f["k_ph15_cos"] = np.cos(2 * np.pi * ph)
    f["k_hora0"] = (m == 0).astype(float)
    f["k_fund_min"] = ((480 - since_fund) % 480) / 480
    f["k_fund0"] = (since_fund == 0).astype(float)
    f["k_fund_post"] = ((since_fund >= 1) & (since_fund <= 5)).astype(float)
    return f[CLOCK]


def _predict(X, y, ok, idx, label_end, start, end, st, ec, log, tag):
    p = np.full(len(idx), np.nan)
    for fold in make_folds(start, end, st["step_months"], st["train_months"], st["calib_frac"]):
        fit, cal, test = fold.masks(idx, label_end)
        valid = ok & ~np.isnan(y) & (y != 0)
        fit_nt, cal_nt, test_ok = fit & valid, cal & valid, test & ok
        if fit_nt.sum() < 1000 or cal_nt.sum() < 300 or test_ok.sum() == 0:
            log(f"  [{tag}] {fold.name}: sin datos suficientes")
            continue
        _, (pc, pt) = fit_predict_proba("gbm", X[fit_nt], (y[fit_nt] == 1).astype(int), [X[cal_nt], X[test_ok]],
                                        seed=ec["seed"], max_rows=st["max_fit_rows"], features=list(X.columns))
        p[test_ok] = Calibrator().fit(pc, (y[cal_nt] == 1).astype(int)).transform(pt)
        log(f"  [{tag}] {fold.name}: ajuste={fit_nt.sum():,} prueba={test_ok.sum():,}")
    return p


def _logloss(p: np.ndarray, y: np.ndarray) -> np.ndarray:
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return -(y * np.log(p) + (1 - y) * np.log(1 - p))


def _policy(p, y, q_hat, idx, contract, margin, payout, n_boot, mask=None):
    sel = ~np.isnan(p) & ~np.isnan(y) & ~np.isnan(q_hat)
    if mask is not None:
        sel &= mask
    side = np.where(p >= 0.5, 1, -1)
    p_dir = np.where(side == 1, p, 1 - p)
    take = sel & (contract.ev(p_dir, np.nan_to_num(q_hat)) >= margin)
    out = _stats(y[take], side[take], idx[take], payout, n_boot)
    return {"acierto": None, "ev": float("nan"), **out}  # sin operaciones: EV indefinido (no pasa ningún «≥»)


def run(root3: Path = Path("data/raw/estudio3"), out_dir: Path = Path("results/estudio33"), n_boot: int = 1000,
        log=print, download: bool = True) -> dict:
    from .study3 import download as dl, load, spot_bars

    if download:
        dl(root3, "2020-12", "2026-09", symbols=(SYMBOL,), kinds=("spot",))
    cfg = load_config("config/research.toml")  # solo se lee
    st, cc, ec = cfg["study"], cfg["contracts"], cfg["execution"]
    payout, margin = cc["binary_payout"], cc["binary_ev_margin"]
    contract = BinaryContract(payout, cc["binary_tie_rule"])
    bars = spot_bars(load(root3, SYMBOL, "spot"))
    bars = bars[(bars.index >= pd.Timestamp(DATA_START, tz="UTC")) & (bars.index < pd.Timestamp(DATA_END, tz="UTC"))]
    idx = bars.index
    pf = compute_features(bars)
    ck = clock_features(idx)
    lab = make_labels(bars, 1, 1, get_instrument(SYMBOL).point)
    y = lab["dir"].to_numpy()
    tie = (lab["dir"] == 0).astype(float).where(lab["dir"].notna())
    q_hat = tie.shift(2).rolling(1440, min_periods=200).mean().to_numpy()  # causal, como el Estudio 13
    label_end = pd.DatetimeIndex(lab["label_end"])
    X0 = pf[FEATURES]
    X1 = pd.concat([X0, ck], axis=1)
    ok = X1.notna().all(axis=1).to_numpy()  # misma muestra para base y nuevo
    q15 = ck["k_q15"].to_numpy() == 1
    fund = (ck["k_fund0"].to_numpy() == 1) | (ck["k_fund_post"].to_numpy() == 1)
    rep = {"estudio": "Estudio 33 — variables de reloj en el GBM de BTC 1 min (pre-registro aea2c8b)",
           "git_sha": git_sha(), "variables": CLOCK, "periodos": PERIODS}
    for per, (a, b) in PERIODS.items():
        p0 = _predict(X0, y, ok, idx, label_end, a, b, st, ec, log, f"base {per}")
        p1 = _predict(X1, y, ok, idx, label_end, a, b, st, ec, log, f"reloj {per}")
        if np.allclose(np.nan_to_num(p0), np.nan_to_num(p1)):
            raise RuntimeError("El modelo con reloj predice igual que el base: revise el ajuste (ítem 39).")
        m = ~np.isnan(p0) & ~np.isnan(p1) & ~np.isnan(y) & (y != 0)
        yy = (y[m] == 1).astype(float)
        bb = block_bootstrap_mean(_logloss(p0[m], yy) - _logloss(p1[m], yy), idx[m].strftime("%G-%V"), n_boot=n_boot)
        both = ~np.isnan(p0) & ~np.isnan(p1)
        e0 = _policy(p0, y, q_hat, idx, contract, margin, payout, n_boot, both)
        e1 = _policy(p1, y, q_hat, idx, contract, margin, payout, n_boot, both)
        info = {}
        for name, mk in (("cuarto_de_hora", q15), ("resto", ~q15), ("financiacion_0_5", fund)):
            info[name] = {"base": _policy(p0, y, q_hat, idx, contract, margin, payout, 200, both & mk),
                          "reloj": _policy(p1, y, q_hat, idx, contract, margin, payout, 200, both & mk)}
        rep[per] = {"minutos": int(m.sum()), "mejora_logloss": bb["mean"], "ic95_logloss": [bb["lo"], bb["hi"]],
                    "base": e0, "reloj": e1, "informativo": info}
        log(f"{per}: Δlog-loss {bb['mean']:+.5f} [{bb['lo']:+.5f}; {bb['hi']:+.5f}] | acierto "
            f"{e0['acierto']} → {e1['acierto']} | EV {e0['ev']:+.4f} → {e1['ev']:+.4f}")
    d, v = rep["desarrollo"], rep["verificacion"]
    crit = {"dev_logloss_ic": d["ic95_logloss"][0] > 0, "dev_ev": d["reloj"]["ev"] >= d["base"]["ev"],
            "verif_logloss": v["mejora_logloss"] > 0, "verif_ev": v["reloj"]["ev"] >= v["base"]["ev"]}
    rep["criterios"], rep["pasa"] = crit, all(crit.values())
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "resultado.json").write_text(json.dumps(jsonable(rep), indent=2, ensure_ascii=False), encoding="utf-8")
    return rep
