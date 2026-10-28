"""Estudio 26 (pre-registro en docs/01, commit a5d8adf): aviso anticipado (receta H16b) + umbral p ≥ 0,60 en XRP, SOL, ETH
y DOGE, repetición mensual 2025-09 → 2026-10-25, con control del «rebote» del último precio.
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
from .models import fit_predict_proba
from .study3 import _read_klines, load, spot_bars
from .study16 import MAX_GAP_S, _read_sec, minute_table, partial_features
from .study20 import evaluate
from .walkforward import make_folds

K, LAT, UMBRAL = 50, 10, 0.60
ALPHA = 0.05 / 4
COINS = {"XRPUSDT": 0.0001, "SOLUSDT": 0.01, "ETHUSDT": 0.01, "DOGEUSDT": 0.00001}  # tic de precio de Binance
WORK = Path("data/processed/estudio26")
MONTHLY = "https://data.binance.vision/data/spot/monthly/klines/{s}/{i}/{s}-{i}-{ym}.zip"
DAILY = "https://data.binance.vision/data/spot/daily/klines/{s}/{i}/{s}-{i}-{d}.zip"
TEST_START, TEST_END = "2025-09-01", "2026-10-26"
ROBUST = [o - j for o in (60, 120) for j in range(5)]


def _get(session, url: str, reader):
    raw = get_bytes(session, url, timeout=300)
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        return reader(zf.read(zf.namelist()[0]))


def download(symbol: str, work: Path = WORK) -> None:
    """Velas de 1 s (2024-09 → 2026-10-25) y de 1 min (2025-09 → 2026-10-25) de Binance."""
    s = make_session()
    for interval, first, reader in (("1s", "2024-09", _read_sec), ("1m", "2025-09", _read_klines)):
        for ym in (p.strftime("%Y-%m") for p in pd.period_range(first, "2026-09", freq="M")):
            f = Path(work) / symbol / interval / f"{ym}.parquet"
            if not f.exists():
                try:
                    df = _get(s, MONTHLY.format(s=symbol, i=interval, ym=ym), reader)
                except NotFound:
                    print(f"  {symbol} {interval} {ym}: no disponible", flush=True)
                    continue
                f.parent.mkdir(parents=True, exist_ok=True)
                df.to_parquet(f)
                print(f"  {symbol} {interval} {ym}: {len(df):,}", flush=True)
        f = Path(work) / symbol / interval / "2026-10.parquet"
        if not f.exists():
            days = pd.date_range("2026-10-01", "2026-10-26", freq="D", inclusive="left")
            pd.concat([_get(s, DAILY.format(s=symbol, i=interval, d=f"{d:%Y-%m-%d}"), reader) for d in days]).to_parquet(f)
            print(f"  {symbol} {interval} 2026-10 (diarios hasta el 25): listo", flush=True)


def last_before(sec: pd.DataFrame, minutes: pd.DatetimeIndex, offs: list[int]) -> pd.DataFrame:
    """Último precio negociado antes de t + o s (regla del Estudio 16: hueco ≤ 5 s)."""
    start = minutes[0]
    grid = pd.date_range(start, minutes[-1] + pd.Timedelta(seconds=max(offs) + 1), freq="s", tz="UTC")
    c = sec["c"].reindex(grid).to_numpy()
    li = pd.Series(np.where(~np.isnan(c), np.arange(len(grid)), np.nan)).ffill().to_numpy()
    base = ((minutes - start) / pd.Timedelta(seconds=1)).to_numpy().astype(np.int64)
    out = pd.DataFrame(index=minutes)
    for o in offs:
        j = base + o - 1
        ok = ~np.isnan(li[j]) & (j - np.nan_to_num(li[j], nan=-1e9) <= MAX_GAP_S)
        out[f"R{o}"] = np.where(ok, c[np.nan_to_num(li[j], nan=0).astype(np.int64)], np.nan)
    return out


def tables(symbol: str, work: Path = WORK) -> pd.DataFrame:
    f = Path(work) / symbol / "tabla.parquet"
    if f.exists():
        return pd.read_parquet(f)
    files = sorted((Path(work) / symbol / "1s").glob("*.parquet"))
    parts = []
    for i, g in enumerate(files):
        sec = pd.read_parquet(g)
        if i + 1 < len(files):
            nxt = pd.read_parquet(files[i + 1])
            sec = pd.concat([sec, nxt[nxt.index < nxt.index[0].floor("min") + pd.Timedelta(minutes=5)]])
        m0 = sec.index[0].floor("min")
        m1 = min(pd.Timestamp(g.stem + "-01", tz="UTC") + pd.offsets.MonthBegin(1), sec.index[-1].floor("min"))
        mins = pd.date_range(m0, m1 - pd.Timedelta(minutes=1), freq="min", tz="UTC")
        parts.append(pd.concat([minute_table(sec, mins), last_before(sec, mins, ROBUST)], axis=1))
        print(f"  {symbol} tabla {g.stem}", flush=True)
    t = pd.concat(parts)
    t = t[~t.index.duplicated(keep="first")].sort_index()
    t.to_parquet(f)
    return t


def label(o: np.ndarray, c: np.ndarray, tick: float) -> np.ndarray:
    d = np.sign(np.round((c - o) / (tick / 2)))
    return np.where(np.isnan(o) | np.isnan(c), np.nan, d)


def run_coin(symbol: str, tick: float, st, cc, ec, log=print) -> dict:
    download(symbol)
    tab = tables(symbol)
    m1 = pd.concat([pd.read_parquet(f) for f in sorted((WORK / symbol / "1m").glob("*.parquet"))])
    spot = pd.concat([load(Path("data/raw/estudio3"), symbol, "spot"), m1])
    spot = spot[~spot.index.duplicated(keep="last")].sort_index()
    bars = spot_bars(spot)
    bars = bars[(bars.index >= pd.Timestamp("2024-08-25", tz="UTC")) & (bars.index < pd.Timestamp(TEST_END, tz="UTC"))]
    tab = tab.reindex(bars.index)
    prev = compute_features(bars).shift(1)
    X = pd.concat([prev[FEATURES], partial_features(tab, bars["o"], np.exp(prev["lvol60"]), K)], axis=1)
    y = label(tab[f"Q{K + LAT}"].to_numpy(), tab[f"Q{K + LAT + 60}"].to_numpy(), tick)
    rob = label(tab[[f"R{60 - j}" for j in range(5)]].mean(axis=1, skipna=False).to_numpy(),
                tab[[f"R{120 - j}" for j in range(5)]].mean(axis=1, skipna=False).to_numpy(), tick)
    tie = pd.Series(np.where(np.isnan(y), np.nan, (y == 0).astype(float)), index=bars.index)
    q_hat = tie.shift(3).rolling(1440, min_periods=200).mean().to_numpy()
    ok = X.notna().all(axis=1).to_numpy() & ~np.isnan(q_hat)
    label_end = pd.DatetimeIndex(bars.index + pd.Timedelta(minutes=3))
    p = np.full(len(bars), np.nan)
    for fold in make_folds(TEST_START, TEST_END, 1, st["train_months"], st["calib_frac"]):
        fit, cal, test = fold.masks(bars.index, label_end)
        valid = ok & ~np.isnan(y) & (y != 0)
        fit_nt, cal_nt, test_ok = fit & valid, cal & valid, test & ok
        _, (pc, pt) = fit_predict_proba("gbm", X[fit_nt], (y[fit_nt] == 1).astype(int), [X[cal_nt], X[test_ok]],
                                        seed=ec["seed"], max_rows=st["max_fit_rows"], features=list(X.columns))
        p[test_ok] = Calibrator().fit(pc, (y[cal_nt] == 1).astype(int)).transform(pt)
        log(f"  [{symbol}] {fold.name}: ajuste={fit_nt.sum():,} prueba={test_ok.sum():,}")
    contract, margin = BinaryContract(cc["binary_payout"], "refund"), cc["binary_ev_margin"]
    sel = ~np.isnan(p)
    t = bars.index[sel]
    main = evaluate(p[sel], y[sel], q_hat[sel], t, contract, margin, 1000, 1 - ALPHA, umbral=UMBRAL)
    robust = evaluate(p[sel], rob[sel], q_hat[sel], t, contract, margin, 200, 0.95, umbral=UMBRAL)
    todas = evaluate(p[sel], y[sel], q_hat[sel], t, contract, margin, 200, 0.95)
    robust_todas = evaluate(p[sel], rob[sel], q_hat[sel], t, contract, margin, 200, 0.95)
    for d in (robust, todas, robust_todas):
        d.pop("mensual")
    be = 1 / (1 + cc["binary_payout"])
    crit = {"min_300": main["operaciones"] >= 300, "p_bonferroni": main["p"] < ALPHA, "wilson": main["lo95"] > be,
            "meses_60": main["meses_ev_positivo"] >= 0.6, "robusta": (robust["acierto"] or 0) > be}
    out = pd.DataFrame({"p": p[sel], "y": y[sel], "rob": rob[sel], "q": q_hat[sel]}, index=t)
    out.to_parquet(WORK / symbol / "predicciones.parquet")
    return {"tic": tick, "tic_relativo_pb": float(tick / np.nanmedian(bars["c"]) * 1e4), **main, "criterios": crit,
            "pasa": all(crit.values()), "etiqueta_robusta": robust, "todas_sin_umbral": todas,
            "todas_sin_umbral_robusta": robust_todas, "empates": float(np.nanmean(y[sel] == 0))}


def run(out_dir: Path = Path("results/estudio26"), log=print) -> dict:
    cfg = load_config("config/research.toml")  # solo se lee
    st, cc, ec = cfg["study"], cfg["contracts"], cfg["execution"]
    rep = {"estudio": "Estudio 26 — aviso anticipado + umbral en otras monedas (pre-registro a5d8adf)",
           "git_sha": git_sha(), "periodo": [TEST_START, "2026-10-25"], "monedas": {}}
    for sym, tick in COINS.items():
        r = run_coin(sym, tick, st, cc, ec, log)
        rep["monedas"][sym] = r
        log(f"{sym}: pasa={r['pasa']} | {r['operaciones']} ops ({r['por_dia']:.1f}/día) acierto {r['acierto']} "
            f"[{r['lo95']:.4f}] EV {r['ev']:+.4f} | robusta {r['etiqueta_robusta']['acierto']} | "
            f"sin umbral {r['todas_sin_umbral']['acierto']} (robusta {r['todas_sin_umbral_robusta']['acierto']})")
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "resultado.json").write_text(json.dumps(jsonable(rep), indent=2, ensure_ascii=False), encoding="utf-8")
    return rep
