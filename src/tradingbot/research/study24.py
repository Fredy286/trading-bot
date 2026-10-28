"""Estudio 24 (pre-registro en docs/01, commit 181a66b): ¿ETH/USDT o BTC/USDC, en los segundos 0–49 de la vela,
mejoran el modelo H16b de BTC/USDT? Repetición mensual (12 meses de entrenamiento) en desarrollo (2024-07 → 2025-08) y
verificación (2025-09 → 2026-10-25).
"""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

from ..data.http import NotFound, get_bytes, make_session
from .calibration import Calibrator
from .contracts import BinaryContract
from .experiment import git_sha, jsonable, load_config
from .features import FEATURES, compute_features
from .metrics import block_bootstrap_mean
from .models import fit_predict_proba
from .study15 import URL
from .study16 import MAX_GAP_S, _read_sec, label, partial_features
from .study20 import _read_days, build_table, evaluate
from .walkforward import make_folds

K, LAT = 50, 10
WORK = Path("data/processed/estudio24")
DAILY = "https://data.binance.vision/data/spot/daily/klines/{s}/1s/{s}-1s-{d}.zip"
PERIODS = {"desarrollo": ("2024-07-01", "2025-09-01"), "verificacion": ("2025-09-01", "2026-10-26")}
OFFS = (30, 40, 45, 50)  # último precio antes de t + o s (o = 50 − 20, 50 − 10, 50 − 5, 50)
ALPHA = 0.025
HYPS = {"H24a": "ETHUSDT", "H24b": "BTCUSDC"}


def download(symbol: str, work: Path = WORK) -> None:
    session = make_session()
    for ym in (p.strftime("%Y-%m") for p in pd.period_range("2023-07", "2026-09", freq="M")):
        f = Path(work) / symbol / f"{ym}.parquet"
        if f.exists():
            continue
        try:
            raw = get_bytes(session, URL.format(s=symbol, ym=ym), timeout=300)
        except NotFound:
            print(f"  {symbol} 1s {ym}: no disponible (404)", flush=True)
            continue
        with zipfile.ZipFile(io.BytesIO(raw)) as zf:
            sec = _read_sec(zf.read(zf.namelist()[0]))[["c"]]
        f.parent.mkdir(parents=True, exist_ok=True)
        sec.to_parquet(f)
        print(f"  {symbol} 1s {ym}: {len(sec):,} segundos", flush=True)
    f = Path(work) / symbol / "2026-10.parquet"
    if not f.exists():
        parts = []
        for d in pd.date_range("2026-10-01", "2026-10-26", freq="D", inclusive="left"):
            raw = get_bytes(session, DAILY.format(s=symbol, d=f"{d:%Y-%m-%d}"), timeout=300)
            with zipfile.ZipFile(io.BytesIO(raw)) as zf:
                parts.append(_read_sec(zf.read(zf.namelist()[0]))[["c"]])
        pd.concat(parts).to_parquet(f)
        print(f"  {symbol} 1s 2026-10 (diarios hasta el 25): listo", flush=True)


def price_points(sec: pd.DataFrame, minutes: pd.DatetimeIndex) -> pd.DataFrame:
    """Último precio negociado antes de t + o s para cada minuto t (misma regla que el Estudio 16)."""
    start = minutes[0]
    grid = pd.date_range(start, minutes[-1] + pd.Timedelta(minutes=1), freq="s", tz="UTC", inclusive="left")
    c = sec["c"].reindex(grid).to_numpy()
    present = ~np.isnan(c)
    last_i = pd.Series(np.where(present, np.arange(len(grid)), np.nan)).ffill().to_numpy()
    base = ((minutes - start) / pd.Timedelta(seconds=1)).to_numpy().astype(np.int64)
    out = pd.DataFrame(index=minutes)
    for o in OFFS:
        j = base + o - 1
        li = last_i[j]
        ok = ~np.isnan(li) & (j - np.nan_to_num(li, nan=-1e9) <= MAX_GAP_S)
        out[f"X{o}"] = np.where(ok, c[np.nan_to_num(li, nan=0).astype(np.int64)], np.nan)
    return out


def points_table(symbol: str, work: Path = WORK) -> pd.DataFrame:
    f = Path(work) / f"puntos_{symbol}.parquet"
    if f.exists():
        return pd.read_parquet(f)
    parts = []
    for g in sorted((Path(work) / symbol).glob("*.parquet")):
        sec = pd.read_parquet(g)
        m0 = sec.index[0].floor("min")
        mins = pd.date_range(m0, sec.index[-1].floor("min"), freq="min", tz="UTC")
        parts.append(price_points(sec, mins))
    t = pd.concat(parts)
    t = t[~t.index.duplicated(keep="first")].sort_index()
    t.to_parquet(f)
    return t


def extra_features(symbol: str, pts: pd.DataFrame, tab: pd.DataFrame, vol: pd.Series, part: pd.DataFrame):
    f = pd.DataFrame(index=tab.index)
    pts = pts.reindex(tab.index)
    if symbol == "ETHUSDT":
        for j, o in ((5, 45), (10, 40), (20, 30)):
            r = np.log(pts["X50"] / pts[f"X{o}"]) / (vol * np.sqrt(j / 60))
            f[f"e_r{j}"] = r
            f[f"e_d{j}"] = r - part[f"p_r{j}"]
    else:
        basis = np.log(pts["X50"] / tab["P50"]) * 1e4
        f["u_basis"] = basis
        f["u_dbasis10"] = basis - np.log(pts["X40"] / tab["P50_m10"]) * 1e4
        f["u_d10"] = np.log(pts["X50"] / pts["X40"]) / (vol * np.sqrt(10 / 60)) - part["p_r10"]
    return f.replace([np.inf, -np.inf], np.nan)


def _predict(X, y, ok, bars, start, end, st, ec, log, tag):
    label_end = pd.DatetimeIndex(bars.index + pd.Timedelta(minutes=3))
    p = np.full(len(bars), np.nan)
    for fold in make_folds(start, end, 1, st["train_months"], st["calib_frac"]):
        fit, cal, test = fold.masks(bars.index, label_end)
        valid = ok & ~np.isnan(y) & (y != 0)
        fit_nt, cal_nt, test_ok = fit & valid, cal & valid, test & ok
        _, (pc, pt) = fit_predict_proba("gbm", X[fit_nt], (y[fit_nt] == 1).astype(int), [X[cal_nt], X[test_ok]],
                                        seed=ec["seed"], max_rows=st["max_fit_rows"], features=list(X.columns))
        p[test_ok] = Calibrator().fit(pc, (y[cal_nt] == 1).astype(int)).transform(pt)
        log(f"  [{tag}] {fold.name}: ajuste={fit_nt.sum():,} prueba={test_ok.sum():,}")
    return p


def run(root3: Path = Path("data/raw/estudio3"), daily: Path = Path("data/processed/senal/diario"),
        out_dir: Path = Path("results/estudio24"), n_boot: int = 1000, log=print) -> dict:
    from .study3 import load, spot_bars

    cfg = load_config("config/research.toml")  # solo se lee
    st, cc, ec = cfg["study"], cfg["contracts"], cfg["execution"]
    contract, margin = BinaryContract(cc["binary_payout"], "refund"), cc["binary_ev_margin"]
    spot = pd.concat([load(root3, "BTCUSDT", "spot"), _read_days(Path(daily) / "1m", "2026-10-01", "2026-10-26")])
    spot = spot[~spot.index.duplicated(keep="last")].sort_index()
    bars = spot_bars(spot)
    bars = bars[(bars.index >= pd.Timestamp("2023-06-24", tz="UTC")) & (bars.index < pd.Timestamp("2026-10-26", tz="UTC"))]
    tab = build_table().reindex(bars.index)
    prev = compute_features(bars).shift(1)
    vol = np.exp(prev["lvol60"])
    part = partial_features(tab, bars["o"], vol, K)
    X0 = pd.concat([prev[FEATURES], part], axis=1)
    y = label(tab, K, LAT)
    tie = pd.Series(np.where(np.isnan(y), np.nan, (y == 0).astype(float)), index=bars.index)
    q_hat = tie.shift(3).rolling(1440, min_periods=200).mean().to_numpy()
    rep = {"estudio": "Estudio 24 — ETH y BTC/USDC en los segundos 0–49 (pre-registro 181a66b)", "git_sha": git_sha(),
           "hipotesis": {}}
    for h, sym in HYPS.items():
        download(sym)
        extra = extra_features(sym, points_table(sym), tab, vol, part)
        X1 = pd.concat([X0, extra], axis=1)
        ok = X1.notna().all(axis=1).to_numpy() & ~np.isnan(q_hat)  # misma muestra para base y nuevo
        res = {}
        for per, (a, b) in PERIODS.items():
            p0 = _predict(X0, y, ok, bars, a, b, st, ec, log, f"{h} base {per}")
            p1 = _predict(X1, y, ok, bars, a, b, st, ec, log, f"{h} nuevo {per}")
            m = ~np.isnan(p0) & ~np.isnan(p1) & ~np.isnan(y) & (y != 0)
            yy = (y[m] == 1).astype(float)
            eps = 1e-6
            ll = lambda p: -(yy * np.log(np.clip(p, eps, 1)) + (1 - yy) * np.log(np.clip(1 - p, eps, 1)))
            delta = ll(p0[m]) - ll(p1[m])
            wk = bars.index[m].strftime("%G-%V")
            bb = block_bootstrap_mean(delta, wk, n_boot=n_boot, level=1 - ALPHA)
            sel = ~np.isnan(p0) & ~np.isnan(p1)
            t = bars.index[sel]
            e0 = evaluate(p0[sel], y[sel], q_hat[sel], t, contract, margin, 200, 0.95)
            e1 = evaluate(p1[sel], y[sel], q_hat[sel], t, contract, margin, 200, 0.95)
            for e in (e0, e1):
                e.pop("mensual")
            res[per] = {"minutos": int(m.sum()), "mejora_logloss": bb["mean"], "ic_logloss": [bb["lo"], bb["hi"]],
                        "base": e0, "nuevo": e1}
            log(f"{h} {per}: Δlog-loss {bb['mean']:+.5f} [{bb['lo']:+.5f}; {bb['hi']:+.5f}] | acierto "
                f"{e0['acierto']:.4f} → {e1['acierto']:.4f} | EV {e0['ev']:+.4f} → {e1['ev']:+.4f}")
        d, v = res["desarrollo"], res["verificacion"]
        crit = {"dev_logloss_ic": d["ic_logloss"][0] > 0, "dev_ev": d["nuevo"]["ev"] >= d["base"]["ev"],
                "verif_logloss": v["mejora_logloss"] > 0, "verif_ev": v["nuevo"]["ev"] >= v["base"]["ev"]}
        rep["hipotesis"][h] = {"mercado": sym, "variables": list(extra.columns), **res, "criterios": crit,
                               "pasa": all(crit.values())}
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "resultado.json").write_text(json.dumps(jsonable(rep), indent=2, ensure_ascii=False), encoding="utf-8")
    return rep
