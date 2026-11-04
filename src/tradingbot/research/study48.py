"""Estudio 48 (pre-registro en docs/01, commit 10677d7): filtro de «racha reciente» del propio GBM de BTC 1 min.

Base: el modelo del Estudio 33 sin variables de reloj (walk-forward trimestral, 12 meses). Para cada operación de la
política base se mira el acierto de las operaciones base anteriores YA RESUELTAS (fin de etiqueta ≤ apertura de t):
H48a, las últimas 500; H48b, las de los 7 días anteriores (≥ 50). Se opera solo si ese acierto ≥ equilibrio.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from ..instruments import get_instrument
from .contracts import BinaryContract
from .experiment import git_sha, jsonable, load_config
from .features import FEATURES, compute_features
from .labels import make_labels
from .study13 import _stats
from .study33 import _predict

SYMBOL = "BTCUSDT"
DATA_START, DATA_END = "2021-01-01", "2026-10-01"  # archivos mensuales hasta 2026-09 (nada posterior al 2026-10-25)
PERIODS = {"desarrollo": ("2022-01-01", "2025-09-01"), "verificacion": ("2025-09-01", "2026-10-01")}
ALPHA = 0.025
N_LAST, DAYS, MIN_DAYS_N = 500, 7, 50
MIN_OPS = 300


def streak_rates(times: pd.DatetimeIndex, label_end: pd.DatetimeIndex, res: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Acierto reciente de las operaciones base para cada operación (en orden temporal).

    `res` = resultado de cada operación base (+1 gana, −1 pierde, 0 empate). Solo cuentan las ya resueltas
    (label_end ≤ times[i]) y sin empate. Devuelve (H48a: últimas N_LAST, H48b: últimos DAYS días con ≥ MIN_DAYS_N);
    NaN donde no está definida.
    """
    res = np.asarray(res, float)
    dec = res != 0
    le = np.asarray(label_end[dec].asi8)
    order = np.argsort(le, kind="stable")
    le = le[order]
    wins = (res[dec] > 0).astype(float)[order]
    cum = np.r_[0.0, np.cumsum(wins)]
    t = np.asarray(times.asi8)
    k = np.searchsorted(le, t, side="right")
    a = np.full(len(t), np.nan)
    ok = k >= N_LAST
    a[ok] = (cum[k[ok]] - cum[k[ok] - N_LAST]) / N_LAST
    lo = np.searchsorted(le, np.asarray((times - pd.Timedelta(days=DAYS)).asi8), side="right")
    n = k - lo
    b = np.full(len(t), np.nan)
    okb = n >= MIN_DAYS_N
    b[okb] = (cum[k[okb]] - cum[lo[okb]]) / n[okb]
    return a, b


def diff_bootstrap(res: np.ndarray, taken: np.ndarray, weeks: np.ndarray, n_boot: int, seed: int = 12345) -> dict:
    """Acierto(tomadas) − acierto(saltadas), remuestreando semanas completas. Límite inferior al 2,5 % (unilateral)."""
    res, taken = np.asarray(res, float), np.asarray(taken, bool)
    dec = res != 0
    win = (res > 0).astype(float)
    codes, uniq = pd.factorize(np.asarray(weeks))
    k = len(uniq)
    wt = np.bincount(codes, weights=win * (taken & dec), minlength=k)
    nt = np.bincount(codes, weights=(taken & dec).astype(float), minlength=k)
    ws = np.bincount(codes, weights=win * (~taken & dec), minlength=k)
    ns = np.bincount(codes, weights=(~taken & dec).astype(float), minlength=k)

    def d(i):
        return wt[i].sum(-1) / np.maximum(nt[i].sum(-1), 1) - ws[i].sum(-1) / np.maximum(ns[i].sum(-1), 1)

    point = float(wt.sum() / max(nt.sum(), 1) - ws.sum() / max(ns.sum(), 1))
    idx = np.random.default_rng(seed).integers(0, k, size=(n_boot, k))
    bs = d(idx)
    return {"diferencia": point, "lo": float(np.quantile(bs, ALPHA)), "hi": float(np.quantile(bs, 1 - ALPHA))}


def persistence(res: np.ndarray, times: pd.DatetimeIndex) -> dict:
    """Informativo: correlación entre el acierto de una semana y el de la siguiente."""
    dec = res != 0
    s = pd.Series((res[dec] > 0).astype(float), index=times[dec])
    w = s.groupby(s.index.strftime("%G-%V")).agg(["mean", "size"])
    w = w[w["size"] >= 100]["mean"]
    return {"semanas": len(w), "correlacion_semana_siguiente": float(w.autocorr(1)) if len(w) > 3 else None,
            "acierto_semanal_min_max": [float(w.min()), float(w.max())] if len(w) else None}


def _quarters(res: np.ndarray, times: pd.DatetimeIndex) -> dict:
    dec = res != 0
    s = pd.Series((res[dec] > 0).astype(float), index=times[dec])
    g = s.groupby(pd.PeriodIndex(s.index.tz_convert(None), freq="Q").astype(str))
    return {q: {"operaciones": len(x), "acierto": float(x.mean())} for q, x in g}


def evaluate_filter(res, times, rate, be, payout, n_boot) -> dict:
    common = ~np.isnan(rate)
    r, t, rt = res[common], times[common], rate[common]
    taken = rt >= be
    side = np.ones(len(r))
    out = {"muestra_comun": int(common.sum()),
           "base": _stats(r, side, t, payout, n_boot),
           "tomadas": _stats(r[taken], side[taken], t[taken], payout, n_boot),
           "saltadas": _stats(r[~taken], side[~taken], t[~taken], payout, n_boot),
           "diferencia_acierto": diff_bootstrap(r, taken, t.strftime("%G-%V"), n_boot),
           "trimestres_tomadas": _quarters(r[taken], t[taken]),
           "trimestres_saltadas": _quarters(r[~taken], t[~taken])}
    return out


def _criteria(dev: dict, ver: dict) -> dict:
    def acc(x, k):
        return x[k].get("acierto") if x[k].get("operaciones", 0) else None

    def ev(x, k):
        return x[k].get("ev", float("nan")) if x[k].get("operaciones", 0) else float("nan")

    vt, vs = acc(ver, "tomadas"), acc(ver, "saltadas")
    return {"dev_diferencia_ic": dev["diferencia_acierto"]["lo"] > 0,
            "dev_ev": ev(dev, "tomadas") > ev(dev, "base"),
            "verif_acierto": vt is not None and vs is not None and vt > vs,
            "verif_ev": ev(ver, "tomadas") > ev(ver, "base"),
            "min_300": all(x[k].get("operaciones", 0) >= MIN_OPS for x in (dev, ver) for k in ("tomadas", "saltadas"))}


def run(root3: Path = Path("data/raw/estudio3"), out_dir: Path = Path("results/estudio48"), n_boot: int = 1000,
        log=print, download: bool = True) -> dict:
    from .study3 import download as dl
    from .study3 import load, spot_bars

    if download:
        dl(root3, "2020-12", "2026-09", symbols=(SYMBOL,), kinds=("spot",))
    cfg = load_config("config/research.toml")  # solo se lee
    st, cc, ec = cfg["study"], cfg["contracts"], cfg["execution"]
    payout, margin = cc["binary_payout"], cc["binary_ev_margin"]
    contract = BinaryContract(payout, cc["binary_tie_rule"])
    be = 1 / (1 + payout)
    bars = spot_bars(load(root3, SYMBOL, "spot"))
    bars = bars[(bars.index >= pd.Timestamp(DATA_START, tz="UTC")) & (bars.index < pd.Timestamp(DATA_END, tz="UTC"))]
    idx = bars.index
    X = compute_features(bars)[FEATURES]
    lab = make_labels(bars, 1, 1, get_instrument(SYMBOL).point)
    y = lab["dir"].to_numpy()
    tie = (lab["dir"] == 0).astype(float).where(lab["dir"].notna())
    q_hat = tie.shift(2).rolling(1440, min_periods=200).mean().to_numpy()  # causal, como el Estudio 33
    label_end = pd.DatetimeIndex(lab["label_end"])
    ok = X.notna().all(axis=1).to_numpy()
    rep = {"estudio": "Estudio 48 — filtro de racha reciente del GBM de BTC 1 min (pre-registro 10677d7)",
           "git_sha": git_sha(), "periodos": PERIODS, "equilibrio": be,
           "reglas": {"H48a": f"últimas {N_LAST} resueltas", "H48b": f"últimos {DAYS} días (≥ {MIN_DAYS_N})"},
           "hipotesis": {"H48a": {}, "H48b": {}}}
    for per, (a, b) in PERIODS.items():
        p = _predict(X, y, ok, idx, label_end, a, b, st, ec, log, per)
        side = np.where(p >= 0.5, 1, -1)
        p_dir = np.where(side == 1, p, 1 - p)
        sel = ~np.isnan(p) & ~np.isnan(y) & ~np.isnan(q_hat)
        take = sel & (contract.ev(p_dir, np.nan_to_num(q_hat)) >= margin)
        res = (y[take] * side[take]).astype(float)
        times, le = idx[take], label_end[take]
        ra, rb = streak_rates(times, le, res)
        rep.setdefault("persistencia", {})[per] = persistence(res, times)
        for h, rate in (("H48a", ra), ("H48b", rb)):
            e = evaluate_filter(res, times, rate, be, payout, n_boot)
            rep["hipotesis"][h][per] = e
            log(f"{h} {per}: base {e['base'].get('acierto')} | tomadas {e['tomadas'].get('acierto')} "
                f"(n={e['tomadas'].get('operaciones', 0)}) | saltadas {e['saltadas'].get('acierto')} "
                f"(n={e['saltadas'].get('operaciones', 0)}) | Δ {e['diferencia_acierto']}")
    for h in ("H48a", "H48b"):
        crit = _criteria(rep["hipotesis"][h]["desarrollo"], rep["hipotesis"][h]["verificacion"])
        rep["hipotesis"][h]["criterios"], rep["hipotesis"][h]["pasa"] = crit, all(crit.values())
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "resultado.json").write_text(json.dumps(jsonable(rep), indent=2, ensure_ascii=False), encoding="utf-8")
    return rep
