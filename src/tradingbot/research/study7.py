"""Estudio 7 (pre-registro en docs/01, commit 1492079): ¿Kronos, los «momentos más parecidos», un Kalman de
tendencia u otro activo (ETH) mejoran la probabilidad del GBM de BTC/USDT a 1 minuto?

Dos pasos, porque Kronos corre en su propio entorno (torch) fuera del proyecto:
1. `prepare`: GBM de referencia en walk-forward (2024-10 → 2025-08), sorteo del conjunto E de 20 000 minutos
   y variables de análogos, Kalman y ETH en E → `data/processed/estudio7/E.parquet`.
   Después, `scripts/estudio7_kronos.py` (entorno de Kronos) añade `data/processed/estudio7/kronos.parquet`.
2. `evaluate`: combinador logístico expansivo por trimestre, criterios fijos → `results/estudio7/dev.json`.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

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

TEST_START, TEST_END = "2024-10-01", "2025-09-01"
EVAL_START = pd.Timestamp("2025-01-01", tz="UTC")  # 2024-T4 solo sirve para ajustar el primer combinador
N_E, SEED = 20_000, 20261025
HORIZON, ENTRY_DELAY = 1, 1
K_NN, PATTERN = 100, 12
ALPHA_K, BETA_K = 0.3, 0.05
TOOLS = {"T7-KRONOS": ["kronos"], "T7-ANALOG": ["analog"], "T7-KALMAN": ["kalman"], "T7-ETH": ["eth_r1", "eth_r5"]}
LEVEL = 1 - 0.05 / len(TOOLS)  # Bonferroni: IC 98,75 %
OUT = Path("data/processed/estudio7")


def kalman_slope(logc: np.ndarray, alpha: float = ALPHA_K, beta: float = BETA_K) -> np.ndarray:
    """Kalman estacionario de nivel y pendiente (filtro α-β / Holt). Sin observación: solo predice."""
    out = np.full(len(logc), np.nan)
    level = slope = np.nan
    for i, y in enumerate(logc):
        if np.isnan(level):
            if not np.isnan(y):
                level, slope = y, 0.0
                out[i] = slope
            continue
        pred = level + slope
        if np.isnan(y):
            level = pred
        else:
            resid = y - pred
            level = pred + alpha * resid
            slope = slope + beta * resid
        out[i] = slope
    return out


def patterns(logc: pd.Series, vol60: pd.Series) -> np.ndarray:
    """Últimos 12 rendimientos de 1 min (t−11 … t) divididos por la vol60 de t."""
    lr = logc.diff()
    cols = [lr.shift(k) / vol60 for k in range(PATTERN)]
    return np.column_stack([c.to_numpy() for c in cols])


def analog_scores(lib_x: np.ndarray, lib_y: np.ndarray, q_x: np.ndarray, k: int = K_NN, chunk: int = 50) -> np.ndarray:
    """Media del signo siguiente (empate = 0) de los k vecinos más cercanos (euclídea) en la biblioteca."""
    lib_x = lib_x.astype(np.float32)
    lib_n = (lib_x ** 2).sum(axis=1)
    out = np.empty(len(q_x))
    for a in range(0, len(q_x), chunk):
        q = q_x[a:a + chunk].astype(np.float32)
        d = lib_n[None, :] - 2 * q @ lib_x.T  # + |q|² no cambia el orden
        idx = np.argpartition(d, k, axis=1)[:, :k]
        out[a:a + chunk] = lib_y[idx].mean(axis=1)
    return out


def prepare(root3: Path = Path("data/raw/estudio3"), out: Path = OUT, log=print) -> pd.DataFrame:
    cfg = load_config("config/research.toml")  # solo se lee: mismo walk-forward y GBM
    st, ec = cfg["study"], cfg["execution"]
    inst = get_instrument("BTCUSDT")
    bars = spot_bars(load(root3, "BTCUSDT", "spot"))
    bars = bars[(bars.index >= pd.Timestamp("2023-09-01", tz="UTC")) & (bars.index < pd.Timestamp(TEST_END, tz="UTC"))]
    pf = compute_features(bars)
    lab = make_labels(bars, HORIZON, ENTRY_DELAY, inst.point)
    y = lab["dir"].to_numpy()
    tie_ind = (lab["dir"] == 0).astype(float).where(lab["dir"].notna())
    q_hat = tie_ind.shift(HORIZON + ENTRY_DELAY).rolling(1440, min_periods=200).mean().to_numpy()  # causal (Fase 1B)
    vol60 = np.exp(pf["lvol60"])
    logc = np.log(bars["c"])
    pat = patterns(logc, vol60)
    pat_ok = ~np.isnan(pat).any(axis=1)
    ok = pf.notna().all(axis=1).to_numpy() & pat_ok
    label_end = pd.DatetimeIndex(lab["label_end"])
    p = np.full(len(bars), np.nan)
    fold_of = np.full(len(bars), "", dtype=object)
    folds = make_folds(TEST_START, TEST_END, st["step_months"], st["train_months"], st["calib_frac"])
    lib = {}
    for fold in folds:
        fit, cal, test = fold.masks(bars.index, label_end)
        valid = ok & ~np.isnan(y) & (y != 0)
        fit_nt, cal_nt, test_ok = fit & valid, cal & valid, test & ok
        y_fit, y_cal = (y[fit_nt] == 1).astype(int), (y[cal_nt] == 1).astype(int)
        _, (pc_raw, pt_raw) = fit_predict_proba("gbm", pf[fit_nt], y_fit, [pf[cal_nt], pf[test_ok]],
                                                seed=ec["seed"], max_rows=st["max_fit_rows"])
        p[test_ok] = Calibrator().fit(pc_raw, y_cal).transform(pt_raw)
        fold_of[test_ok] = fold.name
        # Biblioteca de análogos: los mismos 12 meses (ajuste + calibración) con resultado conocido antes de la prueba.
        in_lib = (fit | cal) & pat_ok & ~np.isnan(y)
        lib[fold.name] = (pat[in_lib], np.sign(y[in_lib]))
        log(f"[GBM] {fold.name}: ajuste={fit_nt.sum():,} calib={cal_nt.sum():,} prueba={test_ok.sum():,} "
            f"biblioteca={in_lib.sum():,}")
    kal = kalman_slope(logc.to_numpy()) / vol60.to_numpy()
    eth = spot_bars(load(root3, "ETHUSDT", "spot")).reindex(bars.index)
    elc = np.log(eth["c"])
    evol = elc.diff().rolling(60, min_periods=50).std()
    evol = evol.where(evol > 0)
    eth_r1 = ((elc - elc.shift(1)) / evol).to_numpy()
    eth_r5 = ((elc - elc.shift(5)) / (evol * np.sqrt(5))).to_numpy()
    # Kronos necesita 512 velas consecutivas completas hasta t (contexto t−511 … t).
    full = bars["c"].notna().astype(int).rolling(512, min_periods=512).sum().to_numpy() == 512
    cand = (~np.isnan(p) & ~np.isnan(y) & ~np.isnan(kal) & ~np.isnan(eth_r1) & ~np.isnan(eth_r5)
            & ~np.isnan(q_hat) & full)
    pos = np.flatnonzero(cand)
    rng = np.random.default_rng(SEED)
    e = np.sort(rng.choice(pos, size=N_E, replace=False))
    df = pd.DataFrame({"time": bars.index[e], "fold": fold_of[e], "p": p[e], "dir": y[e], "q_hat": q_hat[e],
                       "vol60": vol60.to_numpy()[e], "kalman": kal[e], "eth_r1": eth_r1[e], "eth_r5": eth_r5[e]})
    df["analog"] = np.nan
    for name, (lx, ly) in lib.items():
        m = (df["fold"] == name).to_numpy()
        df.loc[m, "analog"] = analog_scores(lx, ly, pat[e[m]])
        log(f"[ANALOG] {name}: {m.sum():,} consultas")
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out / "E.parquet")
    log(f"E: {len(df):,} minutos ({df['time'].min()} → {df['time'].max()}), candidatos {len(pos):,}")
    return df


def _combiner_ll(X_fit: np.ndarray, y_fit: np.ndarray, X_test: np.ndarray) -> np.ndarray:
    m = make_pipeline(StandardScaler(), LogisticRegression(C=1.0, max_iter=1000))
    m.fit(X_fit, y_fit)
    return m.predict_proba(X_test)[:, 1]


def _logit(p: np.ndarray) -> np.ndarray:
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p))


def _policy(p_up: np.ndarray, dirs: np.ndarray, q: np.ndarray, contract: BinaryContract, margin: float) -> dict:
    side = np.where(p_up >= 0.5, 1, -1)
    p_dir = np.where(side == 1, p_up, 1 - p_up)
    take = contract.ev(p_dir, q) >= margin
    d = dirs[take]
    s = side[take]
    wins, ties = int(np.sum(d == s)), int(np.sum(d == 0))
    n = int(take.sum())
    nt = n - ties
    pnl = np.where(d == 0, contract.tie_value, np.where(d == s, contract.payout, -1.0))
    lo, _ = wilson(wins, nt) if nt else (float("nan"), float("nan"))
    return {"operaciones": n, "sin_empate": nt, "aciertos": wins, "acierto": wins / nt if nt else None,
            "lo95": float(lo), "ev": float(pnl.mean()) if n else None}


def evaluate(out: Path = OUT, results: Path = Path("results/estudio7"), n_boot: int = 2000) -> dict:
    cfg = load_config("config/research.toml")
    cc = cfg["contracts"]
    contract = BinaryContract(cc["binary_payout"], cc["binary_tie_rule"])
    df = pd.read_parquet(Path(out) / "E.parquet")
    kr = pd.read_parquet(Path(out) / "kronos.parquet")
    df = df.merge(kr[["time", "kronos_lr"]], on="time", how="left", validate="one_to_one")
    if df["kronos_lr"].isna().any():
        raise RuntimeError(f"Faltan predicciones de Kronos en {int(df['kronos_lr'].isna().sum())} minutos de E.")
    df["kronos"] = df["kronos_lr"] / df["vol60"]
    df = df.sort_values("time").reset_index(drop=True)
    t = pd.DatetimeIndex(df["time"])
    quarters = pd.PeriodIndex(t.tz_convert(None), freq="Q")
    yy = df["dir"].to_numpy()
    nt = yy != 0
    yb = (yy == 1).astype(int)
    lp = _logit(df["p"].to_numpy())
    test = t >= EVAL_START
    probs = {"base": np.full(len(df), np.nan), **{k: np.full(len(df), np.nan) for k in TOOLS}}
    blocks = sorted(set(quarters[test]))
    for qb in blocks:
        tr = (quarters < qb) & nt
        te = quarters == qb
        probs["base"][te] = _combiner_ll(lp[tr, None], yb[tr], lp[te, None])
        for k, cols in TOOLS.items():
            X = np.column_stack([lp, df[cols].to_numpy()])
            probs[k][te] = _combiner_ll(X[tr], yb[tr], X[te])
    sel = test & nt
    y_sel = yb[sel]
    day = t[sel].strftime("%Y-%m-%d")

    def ll(p):
        p = np.clip(p, 1e-6, 1 - 1e-6)
        return -(y_sel * np.log(p) + (1 - y_sel) * np.log(1 - p))

    ll_base = ll(probs["base"][sel])
    q = df["q_hat"].to_numpy()
    base_pol = _policy(probs["base"][test], yy[test], q[test], contract, cc["binary_ev_margin"])
    weekend = (t.dayofweek >= 5)
    res = {}
    for k, cols in TOOLS.items():
        diff = ll_base - ll(probs[k][sel])  # > 0: la herramienta predice mejor
        b = block_bootstrap_mean(diff, day, n_boot=n_boot, level=LEVEL)
        pol = _policy(probs[k][test], yy[test], q[test], contract, cc["binary_ev_margin"])
        c1 = bool(b["lo"] > 0)
        c2 = bool(pol["ev"] is not None and base_pol["ev"] is not None and pol["ev"] >= base_pol["ev"])
        sig = np.sign(df[cols[0]].to_numpy())
        alone = test & nt & (sig != 0)
        res[k] = {"variables": cols, "mejora_logloss": b["mean"], f"ic{LEVEL:.4f}": [b["lo"], b["hi"]],
                  "c1_mejora_logloss": c1, "politica_b": pol, "c2_ev_no_menor": c2, "pasa": c1 and c2,
                  "sola_acierto_signo": float(np.mean(sig[alone] == np.sign(yy[alone]))),
                  "acierto_todas": float(np.mean((probs[k][sel] >= 0.5) == (y_sel == 1))),
                  "por_tipo_de_dia": {
                      n: _policy(probs[k][test & m], yy[test & m], q[test & m], contract, cc["binary_ev_margin"])
                      for n, m in (("entre_semana", ~weekend), ("fin_de_semana", weekend))}}
    report = {"estudio": "Estudio 7 — fase de desarrollo (pre-registro 1492079)", "git_sha": git_sha(),
              "conjunto_E": {"n": len(df), "inicio": str(t.min()), "fin": str(t.max()), "semilla": SEED},
              "prueba": {"desde": str(EVAL_START), "decisiones": int(test.sum()), "sin_empate": int(sel.sum())},
              "nivel_ic": LEVEL,
              "base": {"logloss": float(ll_base.mean()), "politica_b": base_pol,
                       "acierto_todas": float(np.mean((probs["base"][sel] >= 0.5) == (y_sel == 1))),
                       "por_tipo_de_dia": {
                           n: _policy(probs["base"][test & m], yy[test & m], q[test & m], contract,
                                      cc["binary_ev_margin"])
                           for n, m in (("entre_semana", ~weekend), ("fin_de_semana", weekend))}},
              "herramientas": res, "pasa_alguna": any(r["pasa"] for r in res.values())}
    results = Path(results)
    results.mkdir(parents=True, exist_ok=True)
    (results / "dev.json").write_text(json.dumps(jsonable(report), indent=2, ensure_ascii=False), encoding="utf-8")
    return report
