"""Estudio 16 (pre-registro en docs/01, commit dc5ff77): señal anticipada (propuesta P8).

El bot decide en el segundo k de la vela t (k = 55 o 50) con `FEATURES` de la vela t−1 y un bloque parcial de la vela
t medido con velas de 1 s hasta el segundo k. El usuario hace clic L s después (L = 5 o 10): entrada = último
precio negociado antes de t + k + L; vencimiento 60 s después. GBM en walk-forward trimestral, 2024-07 → 2025-08.

Las velas de 1 s se guardan por mes, compactas, en `data/processed/estudio16/seg/<AAAA-MM>.parquet`.
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
from .metrics import binom_pvalue_greater, block_bootstrap_mean, wilson
from .models import fit_predict_proba
from .study3 import load, spot_bars
from .study15 import URL
from .walkforward import make_folds

WORK = Path("data/processed/estudio16")
FIRST_MONTH, LAST_MONTH = "2023-07", "2025-08"
TEST_START, TEST_END, DATA_START = "2024-07-01", "2025-09-01", "2023-06-01"
HYPS = {"H16a": (55, 5), "H16b": (50, 10)}
LATENCIES = (0, 3, 5, 8, 10, 15)
PARTIAL = ["p_ret", "p_clpos", "p_range", "p_r5", "p_r10", "p_r20", "p_tib10", "p_vol10", "p_n10"]
MAX_MISSING, MAX_GAP_S = 10, 5
ALPHA = 0.025
POINT = 0.01


def _read_sec(csv: bytes) -> pd.DataFrame:
    df = pd.read_csv(io.BytesIO(csv), header=None, usecols=[0, 2, 3, 4, 5, 8, 9],
                     names=["t", "h", "l", "c", "v", "n", "tb"])
    if not str(df.iloc[0, 0]).strip().lstrip("-").isdigit():
        df = df.iloc[1:]
    t = pd.to_numeric(df["t"]).astype(np.int64)
    unit = "us" if t.max() > 10**14 else "ms"
    idx = pd.DatetimeIndex(pd.to_datetime(t, unit=unit, utc=True), name="time")
    out = pd.DataFrame({k: pd.to_numeric(df[k]).to_numpy(np.float64) for k in ("h", "l", "c")}, index=idx)
    for k in ("v", "tb", "n"):
        out[k] = pd.to_numeric(df[k]).to_numpy(np.float32)
    return out[~out.index.duplicated(keep="last")].sort_index()


def download(symbol: str = "BTCUSDT", work: Path = WORK, first: str = FIRST_MONTH, last: str = LAST_MONTH) -> None:
    session = make_session()
    for ym in (p.strftime("%Y-%m") for p in pd.period_range(first, last, freq="M")):
        f = Path(work) / "seg" / f"{ym}.parquet"
        if f.exists():
            continue
        try:
            raw = get_bytes(session, URL.format(s=symbol, ym=ym), timeout=300)
        except NotFound:
            print(f"  {symbol} 1s {ym}: no disponible (404)", flush=True)
            continue
        with zipfile.ZipFile(io.BytesIO(raw)) as zf:
            sec = _read_sec(zf.read(zf.namelist()[0]))
        f.parent.mkdir(parents=True, exist_ok=True)
        sec.to_parquet(f)
        print(f"  {symbol} 1s {ym}: {len(sec):,} segundos", flush=True)


def minute_table(sec: pd.DataFrame, minutes: pd.DatetimeIndex) -> pd.DataFrame:
    """Por cada minuto t de `minutes`: bloque parcial crudo para k = 50 y 55 y precios «último antes de t + o s».

    `sec` debe cubrir los minutos pedidos y los 3 minutos siguientes (para las etiquetas).
    """
    start = minutes[0]
    grid = pd.date_range(start, minutes[-1] + pd.Timedelta(minutes=3), freq="s", tz="UTC", inclusive="left")
    s = sec.reindex(grid)
    present = s["c"].notna().to_numpy()
    secs = np.arange(len(grid))
    last_i = pd.Series(np.where(present, secs, np.nan)).ffill().to_numpy()
    c_raw = s["c"].to_numpy()
    h, l = s["h"].to_numpy(), s["l"].to_numpy()
    v, tb, n = (s[k].fillna(0.0).to_numpy(np.float64) for k in ("v", "tb", "n"))
    cv, ctb, cn = (np.r_[0.0, np.cumsum(a)] for a in (v, tb, n))
    base = ((minutes - start) / pd.Timedelta(seconds=1)).to_numpy().astype(np.int64)

    def last_before(off: int) -> np.ndarray:
        """Último precio negociado antes de t + off s (vela de 1 s que abre como mucho en t + off − 1)."""
        j = base + off - 1
        li = last_i[j]
        ok = ~np.isnan(li) & (j - np.nan_to_num(li, nan=-1e9) <= MAX_GAP_S)
        return np.where(ok, c_raw[np.nan_to_num(li, nan=0).astype(np.int64)], np.nan)

    out = pd.DataFrame(index=minutes)
    for k in (50, 55):
        out[f"P{k}"] = last_before(k)
        for j in (5, 10, 20):
            out[f"P{k}_m{j}"] = last_before(k - j)
        win = base[:, None] + np.arange(k)[None, :]
        out[f"hi{k}"] = np.nanmax(np.where(present[win], h[win], np.nan), axis=1)
        out[f"lo{k}"] = np.nanmin(np.where(present[win], l[win], np.nan), axis=1)
        out[f"faltan{k}"] = k - present[win].sum(1)
        a, b, z = base + k - 10, base + k, base
        v10, vk = cv[b] - cv[a], cv[b] - cv[z]
        with np.errstate(invalid="ignore", divide="ignore"):
            out[f"tib10_{k}"] = np.where(v10 > 0, 2 * (ctb[b] - ctb[a]) / v10 - 1, 0.0)
            out[f"vol10_{k}"] = np.where(vk > 0, v10 / vk, np.nan)
            n10, nk = cn[b] - cn[a], cn[b] - cn[z]
            out[f"n10_{k}"] = np.where(nk > 0, n10 / nk, np.nan)
    for k, _ in HYPS.values():
        for lat in LATENCIES:
            for off in (k + lat, k + lat + 60):
                if f"Q{off}" not in out:
                    out[f"Q{off}"] = last_before(off)
    return out


def build_table(work: Path = WORK) -> pd.DataFrame:
    files = sorted((Path(work) / "seg").glob("*.parquet"))
    parts = []
    for i, f in enumerate(files):
        sec = pd.read_parquet(f)
        if i + 1 < len(files):
            nxt = pd.read_parquet(files[i + 1])
            sec = pd.concat([sec, nxt[nxt.index < nxt.index[0].floor("min") + pd.Timedelta(minutes=5)]])
        m0 = sec.index[0].floor("min")
        m1 = pd.Timestamp(f.stem + "-01", tz="UTC") + pd.offsets.MonthBegin(1)
        minutes = pd.date_range(m0, m1 - pd.Timedelta(minutes=1), freq="min", tz="UTC")
        parts.append(minute_table(sec, minutes))
        print(f"  tabla {f.stem}: {len(minutes):,} minutos", flush=True)
    t = pd.concat(parts)
    return t[~t.index.duplicated(keep="first")]


def partial_features(tab: pd.DataFrame, open_t: pd.Series, vol60_prev: pd.Series, k: int) -> pd.DataFrame:
    pk = tab[f"P{k}"]
    f = pd.DataFrame(index=tab.index)
    f["p_ret"] = np.log(pk / open_t) / (vol60_prev * np.sqrt(k / 60))
    rng = tab[f"hi{k}"] - tab[f"lo{k}"]
    f["p_clpos"] = ((pk - tab[f"lo{k}"]) / rng.where(rng > 0)).where(rng > 0, 0.5)
    f["p_range"] = np.log(tab[f"hi{k}"] / tab[f"lo{k}"]) / vol60_prev
    for j in (5, 10, 20):
        f[f"p_r{j}"] = np.log(pk / tab[f"P{k}_m{j}"]) / (vol60_prev * np.sqrt(j / 60))
    f["p_tib10"], f["p_vol10"], f["p_n10"] = tab[f"tib10_{k}"], tab[f"vol10_{k}"], tab[f"n10_{k}"]
    f[tab[f"faltan{k}"] > MAX_MISSING] = np.nan
    return f[PARTIAL].replace([np.inf, -np.inf], np.nan)


def label(tab: pd.DataFrame, k: int, lat: int) -> np.ndarray:
    o, c = tab[f"Q{k + lat}"].to_numpy(), tab[f"Q{k + lat + 60}"].to_numpy()
    d = np.sign(np.round((c - o) / (POINT / 2)))
    return np.where(np.isnan(o) | np.isnan(c), np.nan, d)


def _evaluate(p_up, d, q, times, contract, margin, n_boot):
    side = np.where(p_up >= 0.5, 1, -1)
    take = contract.ev(np.where(side == 1, p_up, 1 - p_up), q) >= margin
    take &= ~np.isnan(d)
    res = d[take] * side[take]
    pnl = np.where(res == 0, 0.0, np.where(res > 0, contract.payout, -1.0))
    n, w = int((res != 0).sum()), int((res > 0).sum())
    lo, hi = wilson(w, n) if n else (float("nan"), float("nan"))
    tt = times[take]
    b = block_bootstrap_mean(pnl, tt.strftime("%G-%V"), n_boot=n_boot, level=1 - ALPHA)
    qs = pd.Series(pnl).groupby(pd.PeriodIndex(tt.tz_convert(None), freq="Q")).sum()
    return {"operaciones": int(take.sum()), "sin_empate": n, "aciertos": w, "acierto": w / n if n else None,
            "lo95": float(lo), "p": binom_pvalue_greater(w, n, 1 / (1 + contract.payout)) if n else 1.0,
            "ev": b["mean"], "ev_ic97_5": [b["lo"], b["hi"]], "trimestres_ev_positivo": float((qs > 0).mean())}


def run(root3: Path = Path("data/raw/estudio3"), work: Path = WORK, out_dir: Path = Path("results/estudio16"),
        n_boot: int = 1000, log=print) -> dict:
    cfg = load_config("config/research.toml")  # solo se lee
    st, cc, ec = cfg["study"], cfg["contracts"], cfg["execution"]
    contract = BinaryContract(cc["binary_payout"], cc["binary_tie_rule"])
    f_tab = Path(work) / "tabla_minutos.parquet"
    if not f_tab.exists():
        build_table(work).to_parquet(f_tab)
    tab = pd.read_parquet(f_tab)
    bars = spot_bars(load(root3, "BTCUSDT", "spot"))
    bars = bars[(bars.index >= pd.Timestamp(DATA_START, tz="UTC")) & (bars.index < pd.Timestamp(TEST_END, tz="UTC"))]
    prev = compute_features(bars).shift(1)  # FEATURES de la vela t−1, ya cerrada en el segundo k de t
    tab = tab.reindex(bars.index)
    vol60_prev = np.exp(prev["lvol60"])
    folds = make_folds(TEST_START, TEST_END, st["step_months"], st["train_months"], st["calib_frac"])
    label_end = pd.DatetimeIndex(bars.index + pd.Timedelta(minutes=3))
    report = {"estudio": "Estudio 16 — señal anticipada (pre-registro dc5ff77)", "git_sha": git_sha(),
              "periodo_prueba": [TEST_START, TEST_END], "hipotesis": {}}
    for hname, (k, lat) in HYPS.items():
        X = pd.concat([prev[FEATURES], partial_features(tab, bars["o"], vol60_prev, k)], axis=1)
        y = label(tab, k, lat)
        tie = pd.Series(np.where(np.isnan(y), np.nan, (y == 0).astype(float)), index=bars.index)
        q_hat = tie.shift(3).rolling(1440, min_periods=200).mean().to_numpy()
        ok = X.notna().all(axis=1).to_numpy() & ~np.isnan(q_hat)
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
        main = _evaluate(p[sel], y[sel], q_hat[sel], times, contract, cc["binary_ev_margin"], n_boot)
        crit = {"min_300": main["operaciones"] >= 300, "p_bonferroni": main["p"] < ALPHA,
                "wilson": main["lo95"] > 1 / (1 + contract.payout), "ev_ic": main["ev_ic97_5"][0] > 0,
                "trimestres_60": main["trimestres_ev_positivo"] >= 0.6}
        sens = {f"L={L}s": _evaluate(p[sel], label(tab, k, L)[sel], q_hat[sel], times, contract,
                                     cc["binary_ev_margin"], 200) for L in LATENCIES}
        report["hipotesis"][hname] = {"k": k, "latencia": lat, **main, "criterios": crit, "pasa": all(crit.values()),
                                      "sensibilidad_latencia": sens}
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "dev.json").write_text(json.dumps(jsonable(report), indent=2, ensure_ascii=False), encoding="utf-8")
    return report
