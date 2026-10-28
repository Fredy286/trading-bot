"""Estudio 19 (pre-registro en docs/01, commit 68db03e): vencimiento fijo cada 15 minutos (binaria de BTC de la
plataforma del usuario, pago 87 %). Se entra R minutos antes del vencimiento: aviso en el segundo 50 de la vela t,
entrada antes de t + 60 s y salida al vencimiento (t + 60 s + R·60 s), solo en las velas cuyo vencimiento cae en un
cuarto de hora exacto. El modelo de cada R se entrena con su etiqueta en todas las velas.
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
from .models import fit_predict_proba
from .study3 import load, spot_bars
from .study16 import DATA_START, TEST_END, TEST_START, WORK, partial_features
from .study18 import K, POINT, _evaluate, price_table
from .walkforward import make_folds

PAYOUT = 0.87
RS = {"H19-R1": 1, "H19-R2": 2, "H19-R3": 3, "H19-R5": 5}
LAT, LATENCIES = 10, (0, 5, 10, 15)
ALPHA = 0.05 / 4


def offsets() -> list[int]:
    out = set()
    for lat in LATENCIES:
        out.add(K + lat)
        for r in RS.values():
            out.add(K + lat + 60 * r)
    return sorted(out)


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
        parts.append(price_table(sec, pd.date_range(m0, m1 - pd.Timedelta(minutes=1), freq="min", tz="UTC"), offs))
        print(f"  precios {f.stem}", flush=True)
    t = pd.concat(parts)
    return t[~t.index.duplicated(keep="first")]


def label(prices: pd.DataFrame, lat: int, r: int) -> np.ndarray:
    o, c = prices[f"Q{K + lat}"].to_numpy(), prices[f"Q{K + lat + 60 * r}"].to_numpy()
    d = np.sign(np.round((c - o) / (POINT / 2)))
    return np.where(np.isnan(o) | np.isnan(c), np.nan, d)


def quarter_aligned(index: pd.DatetimeIndex, r: int) -> np.ndarray:
    """Velas t cuyo vencimiento (inicio de la vela t+1 más R minutos) cae en :00, :15, :30 o :45."""
    return ((index.minute.to_numpy() + 1 + r) % 15) == 0


def run(root3: Path = Path("data/raw/estudio3"), work: Path = WORK, out_dir: Path = Path("results/estudio19"),
        n_boot: int = 1000, log=print) -> dict:
    cfg = load_config("config/research.toml")  # solo se lee
    st, cc, ec = cfg["study"], cfg["contracts"], cfg["execution"]
    contract = BinaryContract(PAYOUT, "refund")
    f_prices = Path(work) / "precios_estudio19.parquet"
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
    report = {"estudio": "Estudio 19 — vencimiento fijo cada 15 min (pre-registro 68db03e)", "git_sha": git_sha(),
              "pago": PAYOUT, "equilibrio": 1 / (1 + PAYOUT), "periodo_prueba": [TEST_START, TEST_END],
              "hipotesis": {}}
    for hname, r in RS.items():
        y = label(prices, LAT, r)
        shift_min = int(np.ceil((K + LAT + 60 * r) / 60)) + 1
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
        sel = ~np.isnan(p) & quarter_aligned(bars.index, r)
        times = bars.index[sel]
        main, _ = _evaluate(p[sel], y[sel], q_hat[sel], times, contract, cc["binary_ev_margin"], n_boot, 1 - ALPHA)
        crit = {"min_300": main["operaciones"] >= 300, "p_bonferroni": main["p"] < ALPHA,
                "wilson": main["lo95"] > 1 / (1 + PAYOUT), "ev_ic": main["ev_ic"][0] > 0,
                "trimestres_60": main["trimestres_ev_positivo"] >= 0.6}
        sens = {f"L={L}s": _evaluate(p[sel], label(prices, L, r)[sel], q_hat[sel], times, contract,
                                     cc["binary_ev_margin"], 200, 0.95)[0] for L in LATENCIES}
        pago85, _ = _evaluate(p[sel], y[sel], q_hat[sel], times, BinaryContract(0.85, "refund"),
                              cc["binary_ev_margin"], 200, 0.95)
        report["hipotesis"][hname] = {"R_min": r, **main, "criterios": crit, "pasa": all(crit.values()),
                                      "sensibilidad_latencia": sens, "pago_85": pago85}
        log(f"{hname}: pasa={all(crit.values())} | {main}")
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "dev.json").write_text(json.dumps(jsonable(report), indent=2, ensure_ascii=False), encoding="utf-8")
    return report
