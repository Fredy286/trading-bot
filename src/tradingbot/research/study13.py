"""Estudio 13 (pre-registro en docs/01, commit ad2e7c3): selector multimoneda.

Para cada moneda del universo fijo, GBM con `FEATURES` en walk-forward trimestral (2022-01 → 2025-08, 12 meses de
entrenamiento, 20 % de calibración isotónica, purga; h = 1, d = 1). En cada minuto se opera solo la moneda con
mayor EV estimado si supera 0,02 (política B), binaria al 85 % con empate reembolsado. Se compara con BTC sola.

Las probabilidades por moneda se guardan en `data/processed/estudio13/<moneda>.parquet` para poder reanudar.
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
from .metrics import block_bootstrap_mean, wilson
from .models import fit_predict_proba
from .study3 import load, spot_bars
from .walkforward import make_folds

UNIVERSE = ("BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "DOGEUSDT", "ADAUSDT")
TEST_START, TEST_END, DATA_START = "2022-01-01", "2025-09-01", "2021-01-01"
WORK = Path("data/processed/estudio13")


def coin_probabilities(symbol: str, root3: Path, cfg: dict, log=print) -> pd.DataFrame:
    """EV estimado, lado y resultado de cada minuto de prueba de una moneda (walk-forward, sin mirar el futuro)."""
    st, cc, ec = cfg["study"], cfg["contracts"], cfg["execution"]
    inst = get_instrument(symbol)
    bars = spot_bars(load(root3, symbol, "spot"))
    bars = bars[(bars.index >= pd.Timestamp(DATA_START, tz="UTC")) & (bars.index < pd.Timestamp(TEST_END, tz="UTC"))]
    pf = compute_features(bars)
    lab = make_labels(bars, 1, 1, inst.point)
    y = lab["dir"].to_numpy()
    tie_ind = (lab["dir"] == 0).astype(float).where(lab["dir"].notna())
    q_hat = tie_ind.shift(2).rolling(1440, min_periods=200).mean().to_numpy()  # causal, como la Fase 1B
    ok = pf.notna().all(axis=1).to_numpy()
    label_end = pd.DatetimeIndex(lab["label_end"])
    p = np.full(len(bars), np.nan)
    for fold in make_folds(TEST_START, TEST_END, st["step_months"], st["train_months"], st["calib_frac"]):
        fit, cal, test = fold.masks(bars.index, label_end)
        valid = ok & ~np.isnan(y) & (y != 0)
        fit_nt, cal_nt, test_ok = fit & valid, cal & valid, test & ok
        if fit_nt.sum() < 1000 or cal_nt.sum() < 300 or test_ok.sum() == 0:
            log(f"[{symbol}] {fold.name}: sin datos suficientes")
            continue
        _, (pc, pt) = fit_predict_proba("gbm", pf[fit_nt], (y[fit_nt] == 1).astype(int), [pf[cal_nt], pf[test_ok]],
                                        seed=ec["seed"], max_rows=st["max_fit_rows"])
        p[test_ok] = Calibrator().fit(pc, (y[cal_nt] == 1).astype(int)).transform(pt)
        log(f"[{symbol}] {fold.name}: ajuste={fit_nt.sum():,} prueba={test_ok.sum():,}")
    keep = ~np.isnan(p) & ~np.isnan(y) & ~np.isnan(q_hat)
    side = np.where(p >= 0.5, 1, -1)
    p_dir = np.where(side == 1, p, 1 - p)
    ev = BinaryContract(cc["binary_payout"], cc["binary_tie_rule"]).ev(p_dir, np.nan_to_num(q_hat))
    return pd.DataFrame({"ev": ev[keep].astype(np.float32), "lado": side[keep].astype(np.int8),
                         "dir": y[keep].astype(np.int8)}, index=bars.index[keep])


def _stats(dirs: np.ndarray, sides: np.ndarray, times: pd.DatetimeIndex, payout: float, n_boot: int) -> dict:
    res = dirs * sides
    pnl = np.where(res == 0, 0.0, np.where(res > 0, payout, -1.0))
    n_all = len(res)
    if not n_all:
        return {"operaciones": 0}
    nt = res != 0
    wins, n = int((res > 0).sum()), int(nt.sum())
    lo, hi = wilson(wins, n) if n else (float("nan"), float("nan"))
    b = block_bootstrap_mean(pnl, times.strftime("%G-%V"), n_boot=n_boot)
    q = pd.Series(pnl).groupby(pd.PeriodIndex(times.tz_convert(None), freq="Q")).sum()
    days = max(len(set(times.strftime("%Y-%m-%d"))), 1)
    return {"operaciones": n_all, "sin_empate": n, "aciertos": wins, "acierto": wins / n if n else None,
            "lo95": float(lo), "hi95": float(hi), "ev": b["mean"], "ev_ic95": [b["lo"], b["hi"]],
            "trimestres_ev_positivo": float((q > 0).mean()), "operaciones_por_dia": n_all / days,
            "ev_total_por_dia": float(pnl.sum() / days)}


def run(root3: Path = Path("data/raw/estudio3"), out_dir: Path = Path("results/estudio13"), work: Path = WORK,
        n_boot: int = 2000, log=print) -> dict:
    cfg = load_config("config/research.toml")  # solo se lee
    cc = cfg["contracts"]
    margin, payout = cc["binary_ev_margin"], cc["binary_payout"]
    work = Path(work)
    work.mkdir(parents=True, exist_ok=True)
    per = {}
    for s in UNIVERSE:
        f = work / f"{s}.parquet"
        if not f.exists():
            coin_probabilities(s, root3, cfg, log).to_parquet(f)
        per[s] = pd.read_parquet(f)
    ev = pd.concat({s: d["ev"] for s, d in per.items()}, axis=1)
    side = pd.concat({s: d["lado"] for s, d in per.items()}, axis=1).reindex(ev.index)
    dirs = pd.concat({s: d["dir"] for s, d in per.items()}, axis=1).reindex(ev.index)
    evm = ev.where(ev >= margin)
    has = evm.notna().any(axis=1).to_numpy()
    pick = evm[has].astype(float).idxmax(axis=1)
    rows = ev.index[has]
    cols = pd.Index(UNIVERSE).get_indexer(pick)
    r = np.arange(len(rows))
    sel_side = side.loc[rows].to_numpy()[r, cols]
    sel_dir = dirs.loc[rows].to_numpy()[r, cols]
    sel = _stats(sel_dir, sel_side, rows, payout, n_boot)
    sel["elecciones_por_moneda"] = pick.value_counts().to_dict()
    singles = {}
    for s, d in per.items():
        m = d["ev"] >= margin
        singles[s] = _stats(d["dir"][m].to_numpy(), d["lado"][m].to_numpy(), d.index[m], payout, n_boot)
    btc = singles["BTCUSDT"]
    be = 1 / (1 + payout)
    crit = {"min_300": sel["operaciones"] >= 300, "wilson": sel["lo95"] > be, "ev_ic_semanal": sel["ev_ic95"][0] > 0,
            "trimestres_60": sel["trimestres_ev_positivo"] >= 0.6, "no_peor_que_btc": sel["ev"] >= btc["ev"]}
    report = {"estudio": "Estudio 13 — selector multimoneda, fase de desarrollo (pre-registro ad2e7c3)",
              "git_sha": git_sha(), "universo": list(UNIVERSE), "periodo_prueba": [TEST_START, TEST_END],
              "selector": sel, "cada_moneda_sola": singles, "criterios": crit, "pasa": all(crit.values())}
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "dev.json").write_text(json.dumps(jsonable(report), indent=2, ensure_ascii=False), encoding="utf-8")
    return report
