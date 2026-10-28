"""Estudio 18 (pre-registro en docs/01, commit 9929035): aviso anticipado (segundo 50, clic 10 s después) con
contratos de BTC que existen en la plataforma del usuario: 3, 5 y 15 minutos.

Variables: las del Estudio 16 con k = 50 (tabla por minuto ya calculada en data/processed/estudio16). Etiquetas: último
precio negociado antes de t + 50 + L s (entrada) y antes de esa hora + duración (salida), con velas de 1 s.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from .calibration import Calibrator
from .contracts import BinaryContract
from .experiment import git_sha, jsonable, load_config
from .features import FEATURES, compute_features
from .metrics import binom_pvalue_greater, block_bootstrap_mean, wilson
from .models import fit_predict_proba
from .study3 import load, spot_bars
from .study16 import DATA_START, MAX_GAP_S, TEST_END, TEST_START, WORK, partial_features
from .walkforward import make_folds

K = 50
LAT, LATENCIES = 10, (0, 5, 10, 15, 20)
DURATIONS = {"H18-3": 180, "H18-5": 300, "H18-15": 900}
ALPHA = 0.05 / 3
POINT = 0.01


def offsets() -> list[int]:
    out = set()
    for lat in LATENCIES:
        out.add(K + lat)
        for d in DURATIONS.values():
            out.add(K + lat + d)
    return sorted(out)


def price_table(sec: pd.DataFrame, minutes: pd.DatetimeIndex, offs: list[int]) -> pd.DataFrame:
    """Último precio negociado antes de t + o s para cada minuto t y desplazamiento o (máx. 5 s de hueco)."""
    start = minutes[0]
    grid = pd.date_range(start, minutes[-1] + pd.Timedelta(seconds=max(offs) + 5), freq="s", tz="UTC",
                         inclusive="left")
    s = sec["c"].reindex(grid)
    present = s.notna().to_numpy()
    last_i = pd.Series(np.where(present, np.arange(len(grid)), np.nan)).ffill().to_numpy()
    c = s.to_numpy()
    base = ((minutes - start) / pd.Timedelta(seconds=1)).to_numpy().astype(np.int64)
    out = pd.DataFrame(index=minutes)
    for o in offs:
        j = base + o - 1
        li = last_i[j]
        ok = ~np.isnan(li) & (j - np.nan_to_num(li, nan=-1e9) <= MAX_GAP_S)
        out[f"Q{o}"] = np.where(ok, c[np.nan_to_num(li, nan=0).astype(np.int64)], np.nan)
    return out


def build_prices(work: Path = WORK) -> pd.DataFrame:
    files = sorted((Path(work) / "seg").glob("*.parquet"))
    offs = offsets()
    margin = pd.Timedelta(seconds=max(offs) + 120)
    parts = []
    for i, f in enumerate(files):
        sec = pd.read_parquet(f, columns=["c"])
        if i + 1 < len(files):
            nxt = pd.read_parquet(files[i + 1], columns=["c"])
            sec = pd.concat([sec, nxt[nxt.index < nxt.index[0] + margin]])
        m0 = sec.index[0].floor("min")
        m1 = pd.Timestamp(f.stem + "-01", tz="UTC") + pd.offsets.MonthBegin(1)
        minutes = pd.date_range(m0, m1 - pd.Timedelta(minutes=1), freq="min", tz="UTC")
        parts.append(price_table(sec, minutes, offs))
        print(f"  precios {f.stem}: {len(minutes):,} minutos", flush=True)
    t = pd.concat(parts)
    return t[~t.index.duplicated(keep="first")]


def label(prices: pd.DataFrame, lat: int, dur: int) -> np.ndarray:
    o, c = prices[f"Q{K + lat}"].to_numpy(), prices[f"Q{K + lat + dur}"].to_numpy()
    d = np.sign(np.round((c - o) / (POINT / 2)))
    return np.where(np.isnan(o) | np.isnan(c), np.nan, d)


def one_at_a_time(times: pd.DatetimeIndex, take: np.ndarray, dur: int) -> np.ndarray:
    """Solo se toma una señal si la operación anterior ya venció (lo realista a mano)."""
    keep = np.zeros(len(take), bool)
    free = pd.Timestamp.min.tz_localize("UTC")
    entry = times + pd.Timedelta(seconds=K + LAT)
    for i in np.flatnonzero(take):
        if entry[i] >= free:
            keep[i] = True
            free = entry[i] + pd.Timedelta(seconds=dur)
    return keep


def _evaluate(p_up, d, q, times, contract, margin, n_boot, level, mask=None):
    side = np.where(p_up >= 0.5, 1, -1)
    take = (contract.ev(np.where(side == 1, p_up, 1 - p_up), q) >= margin) & ~np.isnan(d)
    if mask is not None:
        take &= mask
    res = d[take] * side[take]
    pnl = np.where(res == 0, 0.0, np.where(res > 0, contract.payout, -1.0))
    n, w = int((res != 0).sum()), int((res > 0).sum())
    lo, _ = wilson(w, n) if n else (float("nan"), 0)
    tt = times[take]
    b = block_bootstrap_mean(pnl, tt.strftime("%G-%V"), n_boot=n_boot, level=level)
    qs = pd.Series(pnl).groupby(pd.PeriodIndex(tt.tz_convert(None), freq="Q")).sum()
    days = max(len(set(tt.strftime("%Y-%m-%d"))), 1)
    return {"operaciones": int(take.sum()), "por_dia": int(take.sum()) / days, "acierto": w / n if n else None,
            "lo95": float(lo), "p": binom_pvalue_greater(w, n, 1 / (1 + contract.payout)) if n else 1.0,
            "ev": b["mean"], "ev_ic": [b["lo"], b["hi"]], "trimestres_ev_positivo": float((qs > 0).mean())}, take


def run(root3: Path = Path("data/raw/estudio3"), work: Path = WORK, out_dir: Path = Path("results/estudio18"),
        n_boot: int = 1000, log=print) -> dict:
    cfg = load_config("config/research.toml")  # solo se lee
    st, cc, ec = cfg["study"], cfg["contracts"], cfg["execution"]
    contract = BinaryContract(cc["binary_payout"], cc["binary_tie_rule"])
    f_prices = Path(work) / "precios_estudio18.parquet"
    if not f_prices.exists():
        build_prices(work).to_parquet(f_prices)
    tab = pd.read_parquet(Path(work) / "tabla_minutos.parquet")
    bars = spot_bars(load(root3, "BTCUSDT", "spot"))
    bars = bars[(bars.index >= pd.Timestamp(DATA_START, tz="UTC")) & (bars.index < pd.Timestamp(TEST_END, tz="UTC"))]
    prev = compute_features(bars).shift(1)
    tab = tab.reindex(bars.index)
    prices = pd.read_parquet(f_prices).reindex(bars.index)
    X = pd.concat([prev[FEATURES], partial_features(tab, bars["o"], np.exp(prev["lvol60"]), K)], axis=1)
    folds = make_folds(TEST_START, TEST_END, st["step_months"], st["train_months"], st["calib_frac"])
    report = {"estudio": "Estudio 18 — aviso anticipado a 3, 5 y 15 min (pre-registro 9929035)", "git_sha": git_sha(),
              "periodo_prueba": [TEST_START, TEST_END], "hipotesis": {}}
    for hname, dur in DURATIONS.items():
        y = label(prices, LAT, dur)
        shift_min = int(np.ceil((K + LAT + dur) / 60)) + 1
        tie = pd.Series(np.where(np.isnan(y), np.nan, (y == 0).astype(float)), index=bars.index)
        q_hat = tie.shift(shift_min).rolling(1440, min_periods=200).mean().to_numpy()
        ok = X.notna().all(axis=1).to_numpy() & ~np.isnan(q_hat)
        label_end = pd.DatetimeIndex(bars.index + pd.Timedelta(minutes=shift_min + 1))
        p = np.full(len(bars), np.nan)
        for fold in folds:
            fit, cal, test = fold.masks(bars.index, label_end)
            valid = ok & ~np.isnan(y) & (y != 0)
            fit_nt, cal_nt, test_ok = fit & valid, cal & valid, test & ok
            _, (pc, pt) = fit_predict_proba("gbm", X[fit_nt], (y[fit_nt] == 1).astype(int), [X[cal_nt], X[test_ok]],
                                            seed=ec["seed"], max_rows=st["max_fit_rows"], features=list(X.columns))
            p[test_ok] = Calibrator().fit(pc, (y[cal_nt] == 1).astype(int)).transform(pt)
            log(f"[{hname}] {fold.name}: ajuste={fit_nt.sum():,} prueba={test_ok.sum():,}")
        sel = ~np.isnan(p)
        times = bars.index[sel]
        main, take = _evaluate(p[sel], y[sel], q_hat[sel], times, contract, cc["binary_ev_margin"], n_boot,
                               1 - ALPHA)
        crit = {"min_300": main["operaciones"] >= 300, "p_bonferroni": main["p"] < ALPHA,
                "wilson": main["lo95"] > 1 / (1 + contract.payout), "ev_ic": main["ev_ic"][0] > 0,
                "trimestres_60": main["trimestres_ev_positivo"] >= 0.6}
        single, _ = _evaluate(p[sel], y[sel], q_hat[sel], times, contract, cc["binary_ev_margin"], 200, 0.95,
                              one_at_a_time(times, take, dur))
        sens = {f"L={L}s": _evaluate(p[sel], label(prices, L, dur)[sel], q_hat[sel], times, contract,
                                     cc["binary_ev_margin"], 200, 0.95)[0] for L in LATENCIES}
        pago80, _ = _evaluate(p[sel], y[sel], q_hat[sel], times, BinaryContract(0.80, "refund"), cc["binary_ev_margin"],
                              200, 0.95)
        report["hipotesis"][hname] = {"duracion_s": dur, **main, "criterios": crit, "pasa": all(crit.values()),
                                      "una_a_la_vez": single, "sensibilidad_latencia": sens, "pago_80": pago80}
        log(f"{hname}: pasa={all(crit.values())} | {main}")
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "dev.json").write_text(json.dumps(jsonable(report), indent=2, ensure_ascii=False), encoding="utf-8")
    return report
