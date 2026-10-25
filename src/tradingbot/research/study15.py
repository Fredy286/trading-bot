"""Estudio 15 (pre-registro en docs/01, commit 85b82bb): presión dentro del minuto con velas de 1 s (mejora P1).

Compara, en las mismas decisiones y con walk-forward trimestral (pruebas 2024-07 → 2025-08), el GBM de BTC a
1 minuto con `FEATURES` frente al mismo GBM con 6 variables medidas dentro de la vela de decisión con velas de 1 s:
rendimiento de los últimos 5, 10 y 20 s, desequilibrio comprador agresor y parte del volumen y de las operaciones
de los últimos 10 s.

Las velas de 1 s de cada mes se resumen por minuto en `data/processed/estudio15/seg/<AAAA-MM>.parquet` y el ZIP
original no se guarda (~70 MB por mes).
"""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

from ..data.http import NotFound, get_bytes, make_session
from ..instruments import get_instrument
from .calibration import Calibrator
from .contracts import BinaryContract
from .experiment import git_sha, jsonable, load_config
from .features import FEATURES, compute_features
from .labels import make_labels
from .metrics import block_bootstrap_mean, wilson
from .models import fit_predict_proba
from .study3 import _read_klines, load, spot_bars
from .walkforward import make_folds

URL = "https://data.binance.vision/data/spot/monthly/klines/{s}/1s/{s}-1s-{ym}.zip"
SEC_FEATURES = ["s_r5", "s_r10", "s_r20", "s_tib10", "s_vol10", "s_n10"]
TEST_START, TEST_END, DATA_START = "2024-07-01", "2025-09-01", "2023-06-01"
FIRST_MONTH, LAST_MONTH = "2023-07", "2025-08"
MAX_MISSING = 10
WORK = Path("data/processed/estudio15/seg")


def minute_summary(sec: pd.DataFrame) -> pd.DataFrame:
    """Resumen por minuto de las velas de 1 s (columnas c, volume, trades, taker_buy_base), sin normalizar.

    Cada segundo sin vela toma el cierre anterior y volumen 0. `faltan` = segundos sin vela en el minuto.
    """
    sec = sec[~sec.index.duplicated(keep="last")].sort_index()
    start, end = sec.index[0].floor("min"), sec.index[-1].floor("min") + pd.Timedelta(seconds=59)
    grid = pd.date_range(start, end, freq="s", tz="UTC")
    s = sec.reindex(grid)
    present = s["c"].notna().to_numpy()
    c = s["c"].ffill().to_numpy()
    vol, trades, taker = (s[k].fillna(0.0).to_numpy() for k in ("volume", "trades", "taker_buy_base"))
    n = len(grid) // 60
    C, V, N, T = (a[: n * 60].reshape(n, 60) for a in (c, vol, trades, taker))
    P = present[: n * 60].reshape(n, 60)
    logc = np.log(C)
    out = pd.DataFrame(index=pd.DatetimeIndex(grid[: n * 60 : 60], name="time"))
    for k in (5, 10, 20):
        out[f"lr{k}"] = logc[:, 59] - logc[:, 59 - k]
    v10, t10 = V[:, 50:].sum(1), T[:, 50:].sum(1)
    vtot, ntot = V.sum(1), N.sum(1)
    with np.errstate(invalid="ignore", divide="ignore"):
        out["s_tib10"] = np.where(v10 > 0, 2 * t10 / v10 - 1, 0.0)
        out["s_vol10"] = np.where(vtot > 0, v10 / vtot, np.nan)
        out["s_n10"] = np.where(ntot > 0, N[:, 50:].sum(1) / ntot, np.nan)
    out["faltan"] = 60 - P.sum(1)
    return out


def download_month(symbol: str, ym: str, work: Path = WORK, session=None, progress: bool = True) -> Path | None:
    f = Path(work) / f"{ym}.parquet"
    if f.exists():
        return f
    session = session or make_session()
    try:
        raw = get_bytes(session, URL.format(s=symbol, ym=ym), timeout=300)
    except NotFound:
        if progress:
            print(f"  {symbol} 1s {ym}: no disponible (404)", flush=True)
        return None
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        sec = _read_klines(zf.read(zf.namelist()[0]))
    f.parent.mkdir(parents=True, exist_ok=True)
    minute_summary(sec).to_parquet(f)
    if progress:
        print(f"  {symbol} 1s {ym}: {len(sec):,} segundos → {f.name}", flush=True)
    return f


def download(symbol: str = "BTCUSDT", work: Path = WORK, first: str = FIRST_MONTH, last: str = LAST_MONTH) -> None:
    session = make_session()
    for ym in (p.strftime("%Y-%m") for p in pd.period_range(first, last, freq="M")):
        download_month(symbol, ym, work, session)


def sec_features(idx: pd.DatetimeIndex, summary: pd.DataFrame, vol60: pd.Series) -> pd.DataFrame:
    """Bloque fijo del pre-registro, alineado con las velas de 1 min (fila t = vela de decisión t)."""
    s = summary.reindex(idx)
    f = pd.DataFrame(index=idx)
    for k in (5, 10, 20):
        f[f"s_r{k}"] = s[f"lr{k}"] / (vol60 * np.sqrt(k / 60))
    for k in ("s_tib10", "s_vol10", "s_n10"):
        f[k] = s[k]
    f[(s["faltan"] > MAX_MISSING) | s["faltan"].isna()] = np.nan
    return f[SEC_FEATURES].replace([np.inf, -np.inf], np.nan)


def _ll(p: np.ndarray, y: np.ndarray) -> np.ndarray:
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return -(y * np.log(p) + (1 - y) * np.log(1 - p))


def _policy(p_up, dirs, q, contract, margin, times):
    side = np.where(p_up >= 0.5, 1, -1)
    p_dir = np.where(side == 1, p_up, 1 - p_up)
    take = contract.ev(p_dir, q) >= margin
    res = dirs[take] * side[take]
    pnl = np.where(res == 0, contract.tie_value, np.where(res > 0, contract.payout, -1.0))
    nt = res != 0
    wins, n = int((res > 0).sum()), int(nt.sum())
    lo, hi = wilson(wins, n) if n else (float("nan"), float("nan"))
    qs = pd.Series(pnl).groupby(pd.PeriodIndex(times[take].tz_convert(None), freq="Q")).sum()
    return {"operaciones": int(take.sum()), "sin_empate": n, "aciertos": wins, "acierto": wins / n if n else None,
            "lo95": float(lo), "ev": float(pnl.mean()) if len(pnl) else None,
            "trimestres_ev_positivo": float((qs > 0).mean()) if len(qs) else 0.0}


def run(root3: Path = Path("data/raw/estudio3"), work: Path = WORK, out_dir: Path = Path("results/estudio15"),
        n_boot: int = 1000, log=print) -> dict:
    cfg = load_config("config/research.toml")  # solo se lee
    st, cc, ec = cfg["study"], cfg["contracts"], cfg["execution"]
    contract = BinaryContract(cc["binary_payout"], cc["binary_tie_rule"])
    bars = spot_bars(load(root3, "BTCUSDT", "spot"))
    bars = bars[(bars.index >= pd.Timestamp(DATA_START, tz="UTC")) & (bars.index < pd.Timestamp(TEST_END, tz="UTC"))]
    pf = compute_features(bars)
    summary = pd.concat(pd.read_parquet(f) for f in sorted(Path(work).glob("*.parquet")))
    summary = summary[~summary.index.duplicated(keep="last")]
    sf = sec_features(bars.index, summary, np.exp(pf["lvol60"]))
    lab = make_labels(bars, 1, 1, get_instrument("BTCUSDT").point)
    y = lab["dir"].to_numpy()
    tie_ind = (lab["dir"] == 0).astype(float).where(lab["dir"].notna())
    q_hat = tie_ind.shift(2).rolling(1440, min_periods=200).mean().to_numpy()
    ok = pf.notna().all(axis=1).to_numpy() & sf.notna().all(axis=1).to_numpy() & ~np.isnan(q_hat)
    X = {"referencia": pf[FEATURES], "prueba": pd.concat([pf[FEATURES], sf], axis=1)}
    label_end = pd.DatetimeIndex(lab["label_end"])
    p = {m: np.full(len(bars), np.nan) for m in X}
    folds_log = []
    for fold in make_folds(TEST_START, TEST_END, st["step_months"], st["train_months"], st["calib_frac"]):
        fit, cal, test = fold.masks(bars.index, label_end)
        valid = ok & ~np.isnan(y) & (y != 0)
        fit_nt, cal_nt, test_ok = fit & valid, cal & valid, test & ok & ~np.isnan(y)
        for m, Xm in X.items():
            _, (pc, pt) = fit_predict_proba("gbm", Xm[fit_nt], (y[fit_nt] == 1).astype(int), [Xm[cal_nt], Xm[test_ok]],
                                            seed=ec["seed"], max_rows=st["max_fit_rows"], features=list(Xm.columns))
            p[m][test_ok] = Calibrator().fit(pc, (y[cal_nt] == 1).astype(int)).transform(pt)
        folds_log.append({"fold": fold.name, "ajuste": int(fit_nt.sum()), "prueba": int(test_ok.sum())})
        log(f"[BTC 1 s] {fold.name}: ajuste={fit_nt.sum():,} prueba={test_ok.sum():,}")
    sel = ~np.isnan(p["referencia"])
    if np.allclose(p["referencia"][sel], p["prueba"][sel]):
        raise RuntimeError("Los dos modelos predicen igual: el bloque nuevo no llegó al ajuste (ítem 39).")
    times = bars.index[sel]
    pol = {m: _policy(p[m][sel], y[sel], q_hat[sel], contract, cc["binary_ev_margin"], times) for m in X}
    nt = y[sel] != 0
    yb = (y[sel][nt] == 1).astype(float)
    diff = _ll(p["referencia"][sel][nt], yb) - _ll(p["prueba"][sel][nt], yb)
    b = block_bootstrap_mean(diff, times[nt].strftime("%Y-%m-%d"), n_boot=n_boot)
    t = pol["prueba"]
    crit = {"min_300": t["operaciones"] >= 300, "wilson": t["lo95"] > 1 / (1 + cc["binary_payout"]),
            "mejora_logloss": b["lo"] > 0, "ev_no_menor": (t["ev"] or -9) >= (pol["referencia"]["ev"] or -9),
            "trimestres_60": t["trimestres_ev_positivo"] >= 0.6}
    acc = {m: float(np.mean((p[m][sel][nt] >= 0.5) == (yb == 1))) for m in X}
    report = {"estudio": "Estudio 15 — velas de 1 s, fase de desarrollo (pre-registro 85b82bb)", "git_sha": git_sha(),
              "periodo_prueba": [TEST_START, TEST_END], "bloque": SEC_FEATURES, "folds": folds_log,
              "decisiones": int(sel.sum()), "politica_b": pol, "acierto_todas_las_decisiones": acc,
              "mejora_logloss": {"media": b["mean"], "ic95": [b["lo"], b["hi"]]}, "criterios": crit,
              "pasa": all(crit.values())}
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "dev.json").write_text(json.dumps(jsonable(report), indent=2, ensure_ascii=False), encoding="utf-8")
    # Predicciones de prueba, para la verificación adversaria (fugas y retraso de entrada).
    pd.DataFrame({"p_ref": p["referencia"][sel], "p_prueba": p["prueba"][sel], "dir": y[sel], "q": q_hat[sel]},
                 index=times).to_parquet(Path(work).parent / "predicciones_dev.parquet")
    return report
