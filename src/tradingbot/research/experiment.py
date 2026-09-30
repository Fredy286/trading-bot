"""Orquestación del estudio pre-registrado para un instrumento.

Flujo: velas → forma canónica → bloqueo del periodo final (en desarrollo) → variables causales →
para cada horizonte: etiquetas, particiones walk-forward, ajuste/calibración/predicción →
simulación de ejecución por contrato y política → métricas con incertidumbre.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import subprocess
import time
import tomllib
from pathlib import Path

import numpy as np
import pandas as pd

from .. import __version__
from ..data.clean import to_canonical
from ..instruments import get_instrument
from .calibration import Calibrator
from .contracts import BinaryContract, SpotContract
from .features import compute_features, rolling_abs_move
from .illusion import asymmetric_exit_demo
from .labels import decision_mask, make_labels
from .metrics import (binom_pvalue_greater, block_bootstrap_mean, brier, log_loss, max_drawdown,
                      reliability, wilson)
from .models import PROB_MODELS, RULES, fit_predict_proba, rule_direction
from .news import trade_overlaps_window
from .simulate import STATUS, ExecParams, max_age_for_horizon, simulate
from .walkforward import enforce_lock, stage_folds

REFERENCES = ["random", "majority"]
SENSITIVITY_POLICIES = {"B_lat60", "B_tieloss"}


def load_config(path: str | Path = "config/research.toml") -> dict:
    with open(path, "rb") as fh:
        return tomllib.load(fh)


def config_hash(cfg: dict) -> str:
    return hashlib.sha256(json.dumps(cfg, sort_keys=True).encode()).hexdigest()[:12]


def git_sha() -> str:
    if os.environ.get("GITHUB_SHA"):
        return os.environ["GITHUB_SHA"]
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:  # pragma: no cover
        return "desconocido"


def jsonable(obj):
    """Convierte tipos numpy/pandas a JSON (NaN/inf → None)."""
    if isinstance(obj, dict):
        return {str(k): jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [jsonable(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating, float)):
        v = float(obj)
        return None if (math.isnan(v) or math.isinf(v)) else v
    if isinstance(obj, np.bool_):
        return bool(obj)
    if isinstance(obj, pd.Timestamp):
        return obj.isoformat()
    if isinstance(obj, pd.DataFrame):
        return jsonable(obj.to_dict(orient="records"))
    return obj


def _group_stats(key: np.ndarray, pnl: np.ndarray, win: np.ndarray) -> dict:
    out = {}
    if len(key) == 0:
        return out
    df = pd.DataFrame({"k": key, "pnl": pnl, "win": win})
    for k, g in df.groupby("k"):
        out[str(k)] = {"n": int(len(g)), "hit": float(g["win"].mean()), "ev": float(g["pnl"].mean()),
                       "sum": float(g["pnl"].sum())}
    return out


def summarize(sim: dict, contract, times: pd.DatetimeIndex, hour_b: np.ndarray, day: np.ndarray,
              fold_id: np.ndarray, regime: np.ndarray, tie_rate_hint: float, n_boot: int) -> dict:
    st, pnl, ex, realized = sim["status"], sim["pnl"], sim["executed"], sim["realized"]
    rec: dict = {"counts": {STATUS[k]: int((st == k).sum()) for k in STATUS}}
    n = int(ex.sum())
    rec["n_trades"] = n
    p = pnl[ex]
    r = realized[ex]
    if isinstance(contract, BinaryContract):
        wins = int(np.sum(p > 0))
        ties = int(np.sum(r == 0))
        losses = n - wins - ties
        n_nt = wins + losses
        lo, hi = wilson(wins, n_nt) if n_nt else (float("nan"), float("nan"))
        be = contract.breakeven(tie_rate_hint)
        rec.update({"wins": wins, "losses": losses, "ties": ties, "hit": wins / n_nt if n_nt else float("nan"),
                    "hit_lo95": lo, "hit_hi95": hi, "breakeven": be,
                    "pvalue": binom_pvalue_greater(wins, n_nt, be) if n_nt else 1.0,
                    "tie_rate": ties / n if n else float("nan")})
        win_flag = p > 0
    else:
        wins = int(np.sum(p > 0))
        lo, hi = wilson(wins, n) if n else (float("nan"), float("nan"))
        rec.update({"wins": wins, "hit": wins / n if n else float("nan"), "hit_lo95": lo, "hit_hi95": hi})
        win_flag = p > 0
    boot = block_bootstrap_mean(p, day[ex], n_boot=n_boot) if n else {"mean": float("nan"), "lo": float("nan"),
                                                                        "hi": float("nan"), "p_le_0": 1.0}
    rec.update({"ev": boot["mean"], "ev_lo95": boot["lo"], "ev_hi95": boot["hi"], "total": float(np.sum(p)),
                "max_drawdown": max_drawdown(p)})
    if not isinstance(contract, BinaryContract):
        rec["pvalue"] = boot["p_le_0"]
    folds = _group_stats(fold_id[ex], p, win_flag)
    rec["by_fold"] = folds
    if folds:
        evs = np.array([v["ev"] for v in folds.values()])
        sums = np.array([v["sum"] for v in folds.values()])
        rec["positive_fold_frac"] = float(np.mean(evs > 0))
        total = sums.sum()
        rec["max_fold_profit_share"] = float(sums.max() / total) if total > 0 else float("nan")
    rec["by_hour_bogota"] = _group_stats(hour_b[ex], p, win_flag)
    rec["by_vol_regime"] = _group_stats(regime[ex], p, win_flag)
    return rec


def run_symbol(symbol: str, raw: pd.DataFrame, stage: str, cfg: dict, n_boot: int = 1000,
               log=print, source: str | None = None) -> dict:
    t0 = time.time()
    inst = get_instrument(symbol)
    source = source or inst.source
    st, cc, ec = cfg["study"], cfg["contracts"], cfg["execution"]
    # HistData omite los minutos sin ticks: se reconstruyen como velas planas (ver clean.py).
    bars, quality = to_canonical(raw, fill_gaps=(source == "histdata"))
    bars = bars[bars.index >= pd.Timestamp(st["data_start"], tz="UTC")]
    bars = enforce_lock(bars, stage, st)
    log(f"[{symbol}] velas: {len(bars):,} minutos en rejilla, calidad: {quality}")
    feats = compute_features(bars)
    folds = stage_folds(stage, st)
    binary = BinaryContract(cc["binary_payout"], cc["binary_tie_rule"])
    spot = SpotContract(commission_px=inst.commission_px, commission_bps=inst.commission_bps)
    local_b = bars.index.tz_convert("America/Bogota")
    hour_b_all = local_b.hour.to_numpy()
    # Clave de día (Bogotá) independiente de la resolución interna de las marcas de tiempo.
    day_all = (local_b.year * 10000 + local_b.month * 100 + local_b.day).to_numpy().astype(np.int64)
    out: dict = {"symbol": symbol, "stage": stage, "source": source,
                 "price": "BID (spread supuesto)" if source == "histdata" else
                 ("negociado (sin bid/ask)" if source == "binance" else "medio (bid+ask)/2"),
                 "code_version": __version__, "git_sha": git_sha(),
                 "config_hash": config_hash(cfg), "quality": quality, "horizons": {},
                 "folds": [{"name": f.name, "train_start": f.train_start, "calib_start": f.calib_start,
                            "test_start": f.test_start, "test_end": f.test_end} for f in folds]}

    for h in st["horizons"]:
        th = time.time()
        lab1 = make_labels(bars, h, 1, inst.point)
        lab2 = make_labels(bars, h, 2, inst.point)
        news = trade_overlaps_window(bars.index, 1, h)
        absmove_bps = (rolling_abs_move(bars, h) / bars["c"] * 1e4).to_numpy()
        tie_ind = (lab1["dir"] == 0).astype(float).where(lab1["dir"].notna())
        q_hat = tie_ind.shift(h + 1).rolling(1440, min_periods=200).mean().to_numpy()  # causal
        cost_now = spot.cost_bps(bars["c"].to_numpy(), bars["spread_c"].to_numpy())

        dm = decision_mask(bars.index, h) & feats.notna().all(axis=1).to_numpy()
        rows = np.flatnonzero(dm)
        idx = bars.index[rows]
        X = feats.iloc[rows]
        L1, L2 = lab1.iloc[rows], lab2.iloc[rows]
        y = L1["dir"].to_numpy()
        n_rows = len(rows)
        preds = {m: {"side": np.zeros(n_rows, dtype=np.float32)} for m in RULES}
        for m in PROB_MODELS:
            preds[m] = {"side": np.zeros(n_rows, dtype=np.float32), "p_dir": np.full(n_rows, np.nan),
                        "conf": np.full(n_rows, np.nan),
                        "thr": {c: np.full(n_rows, np.nan, dtype=np.float32)
                                for c in cfg["acceptance"]["coverage_levels"]}}
        fold_id = np.full(n_rows, -1)
        regime = np.full(n_rows, -1)
        fold_notes = []
        label_end = pd.DatetimeIndex(L1["label_end"])
        for fi, fold in enumerate(folds):
            fit, cal, test = fold.masks(idx, label_end)
            valid = ~np.isnan(y) & (y != 0)
            fit_nt, cal_nt = fit & valid, cal & valid
            if test.sum() == 0 or fit_nt.sum() < 1000 or cal_nt.sum() < 300:
                fold_notes.append({"fold": fold.name, "skipped": True, "fit": int(fit_nt.sum()),
                                   "cal": int(cal_nt.sum()), "test": int(test.sum())})
                continue
            fold_id[test] = fi
            y_fit = (y[fit_nt] == 1).astype(int)
            y_cal = (y[cal_nt] == 1).astype(int)
            lv = X["lvol60"].to_numpy()
            t1, t2 = np.quantile(lv[fit_nt], [1 / 3, 2 / 3])
            regime[test] = np.digitize(lv[test], [t1, t2])
            Xt = X[test]
            for r in RULES:
                preds[r]["side"][test] = rule_direction(r, Xt, y_fit=y_fit, seed=ec["seed"] + fi)
            for m in PROB_MODELS:
                _, (p_cal_raw, p_test_raw) = fit_predict_proba(m, X[fit_nt], y_fit, [X[cal_nt], Xt],
                                                               seed=ec["seed"], max_rows=st["max_fit_rows"])
                calib = Calibrator().fit(p_cal_raw, y_cal)
                p_up = calib.transform(p_test_raw)
                side = np.sign(p_up - 0.5)
                preds[m]["side"][test] = side
                preds[m]["p_dir"][test] = np.where(side >= 0, p_up, 1 - p_up)
                preds[m]["conf"][test] = np.maximum(p_up, 1 - p_up)
                pc = calib.transform(p_cal_raw)
                conf_cal = np.maximum(pc, 1 - pc)
                for c in cfg["acceptance"]["coverage_levels"]:
                    preds[m]["thr"][c][test] = np.quantile(conf_cal, 1 - c)
            fold_notes.append({"fold": fold.name, "skipped": False, "fit": int(fit_nt.sum()),
                               "cal": int(cal_nt.sum()), "test": int(test.sum()),
                               "fit_subsampled": bool(fit_nt.sum() > st["max_fit_rows"])})
            log(f"[{symbol}] h={h} fold {fold.name}: ajuste={fit_nt.sum():,} calib={cal_nt.sum():,} "
                f"prueba={test.sum():,}")

        sub = fold_id >= 0
        hres: dict = {"n_decisions_total": int(n_rows), "n_decisions_test": int(sub.sum()), "folds": fold_notes}
        if sub.sum() == 0:
            out["horizons"][str(h)] = hres
            continue
        rs = rows[sub]
        times = idx[sub]
        hour_b, day = hour_b_all[rs], day_all[rs]
        fsub, rsub = fold_id[sub], regime[sub]
        lbd = {1: L1[sub], 2: L2[sub]}
        news_sub = news[rs]
        q_sub = np.nan_to_num(q_hat[rs], nan=np.nanmean(q_hat) if np.isfinite(np.nanmean(q_hat)) else 0.0)
        move_sub, cost_sub = absmove_bps[rs], cost_now[rs]
        tie_hint = float(np.nanmean((L1["dir"].to_numpy()[sub] == 0)))
        base_exec = dict(latency_median_s=ec["latency_median_s"], latency_sigma=ec["latency_sigma"],
                         max_age_s=max_age_for_horizon(h, ec["max_age_base_s"]),
                         p_disconnect=ec["p_disconnect"], seed=ec["seed"] + h)

        records = []
        for contract in (binary, spot):
            for m in RULES + PROB_MODELS:
                side = preds[m]["side"][sub]
                pols = ["A"] if m in RULES else ["A", "B", "BN", "B_lat60", "B_tieloss"]
                for pol in pols:
                    if pol == "B_tieloss" and not isinstance(contract, BinaryContract):
                        continue
                    want = np.ones(len(side), dtype=bool)
                    block = np.zeros(len(side), dtype=bool)
                    ctr = contract
                    labels = lbd
                    if pol != "A":
                        p_dir = preds[m]["p_dir"][sub]
                        if pol == "B_tieloss":
                            ctr = BinaryContract(contract.payout, "loss")
                        if isinstance(ctr, BinaryContract):
                            want = ctr.ev(p_dir, q_sub) >= cc["binary_ev_margin"]
                        else:
                            want = ctr.ev_bps(p_dir, move_sub, cost_sub) >= cc["spot_ev_margin_frac"] * cost_sub
                        if pol == "BN":
                            block = news_sub
                        if pol == "B_lat60":
                            labels = {1: lbd[2]}
                    sim = simulate(side, want, block, labels, ctr, ExecParams(**base_exec))
                    rec = summarize(sim, ctr, times, hour_b, day, fsub, rsub, tie_hint, n_boot)
                    rec.update({"symbol": symbol, "horizon": h, "contract": contract.name, "model": m,
                                "policy": pol, "sensitivity": pol in SENSITIVITY_POLICIES,
                                "is_reference": m in REFERENCES})
                    records.append(rec)
        hres["evaluations"] = records

        # Precisión pura por cobertura (sin costos ni ejecución) y calibración, para modelos probabilísticos.
        realized = L1["dir"].to_numpy()[sub]
        nt = ~np.isnan(realized) & (realized != 0)
        hres["coverage"], hres["calibration"], hres["payout_grid"] = {}, {}, {}
        for m in PROB_MODELS:
            side = preds[m]["side"][sub]
            conf = preds[m]["conf"][sub]
            rows_cov = []
            for c in cfg["acceptance"]["coverage_levels"]:
                sel = (conf >= preds[m]["thr"][c][sub]) & nt & (side != 0)
                k = int(np.sum(side[sel] == realized[sel]))
                n = int(sel.sum())
                lo, hi = wilson(k, n) if n else (float("nan"), float("nan"))
                rows_cov.append({"target_coverage": c, "realized_coverage": float(sel.sum() / max(nt.sum(), 1)),
                                 "n": n, "hit": k / n if n else float("nan"), "lo95": lo, "hi95": hi})
            hres["coverage"][m] = rows_cov
            p_dir = preds[m]["p_dir"][sub]
            p_up = np.where(side >= 0, p_dir, 1 - p_dir)
            y_up = (realized == 1).astype(float)
            tab, ece = reliability(p_up[nt], y_up[nt], 10)
            hres["calibration"][m] = {"ece": ece, "brier": brier(p_up[nt], y_up[nt]), "brier_const_0_5": 0.25,
                                      "log_loss": log_loss(p_up[nt], y_up[nt]), "n": int(nt.sum()),
                                      "reliability": tab}
            ok = nt | (realized == 0)
            wins = int(np.sum((side == realized) & nt))
            ties = int(np.sum((realized == 0) & ok & (side != 0)))
            losses = int(np.sum(nt & (side != realized) & (side != 0)))
            n_all = wins + ties + losses
            hres["payout_grid"][m] = [{"payout": b, "breakeven": 1 / (1 + b),
                                       "ev_refund": (wins * b - losses) / n_all if n_all else float("nan"),
                                       "ev_tie_loss": (wins * b - losses - ties) / n_all if n_all else float("nan")}
                                      for b in cc["payout_grid"]]

        # Descriptivos: movimiento medio vs costo por hora (base del umbral de contado).
        mv = np.abs(L1["move"].to_numpy()[sub]) / L1["entry"].to_numpy()[sub] * 1e4
        # Costo ida y vuelta ≈ spread observado en la entrada + comisión.
        cst = spot.cost_bps(L1["entry"].to_numpy()[sub], L1["spread_in"].to_numpy()[sub])
        dfd = pd.DataFrame({"hour": hour_b, "move": mv, "cost": cst, "tie": realized == 0}).dropna()
        desc = {"mean_abs_move_bps": float(dfd["move"].mean()), "mean_cost_bps": float(dfd["cost"].mean()),
                "tie_rate": float(dfd["tie"].mean())}
        desc["spot_breakeven"] = SpotContract.breakeven(desc["mean_abs_move_bps"], desc["mean_cost_bps"])
        byh = dfd.groupby("hour").agg(move=("move", "mean"), cost=("cost", "mean"), tie=("tie", "mean"),
                                      n=("move", "size"))
        byh["spot_breakeven"] = 0.5 + byh["cost"] / (2 * byh["move"])
        desc["by_hour_bogota"] = byh.reset_index()
        hres["descriptive"] = desc
        hres["runtime_s"] = time.time() - th
        out["horizons"][str(h)] = hres
        log(f"[{symbol}] h={h} listo en {hres['runtime_s']:.0f}s")

    if stage == "dev":
        try:
            out["illusion_demo"] = asymmetric_exit_demo(bars, inst)
        except Exception as exc:  # pragma: no cover - informativo, no debe tumbar el estudio
            out["illusion_demo"] = {"error": str(exc)}
    out["runtime_s"] = time.time() - t0
    return jsonable(out)
