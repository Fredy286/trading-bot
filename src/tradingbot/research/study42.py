"""Estudio 42 (pre-registro en docs/01, commit 78891ce): blitz de BTC de IQ Option (3 min desde la compra, pago 86 %)
con un modelo que aprende con el precio compuesto (promedio de los cierres de 1 min de Binance, Bybit y OKX), con la
receta del Estudio 20: GBM mes a mes, 2025-09 → 2026-10-25, 12 meses de entrenamiento y purga de 5 min.
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
from .study16 import partial_features
from .study20 import K, TEST_END, TEST_START, _read_days, build_table, evaluate
from .study34 import one_at_a_time
from .study41 import VENUES, composite, month_closes
from .walkforward import make_folds

PAYOUT, DUR, ALPHA, UMBRAL = 0.86, 3, 0.05 / 2, 0.60
COMP = ["c_r1", "c_r3", "c_disp"]


def closes(first: str = "2024-08", last: str = "2026-10") -> dict[str, pd.Series]:
    months = [p.strftime("%Y-%m") for p in pd.period_range(first, last, freq="M")]
    out = {}
    for v in VENUES:
        x = pd.concat([month_closes(v, m) for m in months]).sort_index()
        out[v] = x[~x.index.duplicated(keep="last")]
    return out


def comp_features(comp: pd.Series, binance: pd.Series, vol_prev: pd.Series, index: pd.DatetimeIndex) -> pd.DataFrame:
    """Variables del compuesto conocidas en el segundo 50 de t (solo cierres hasta t − 1)."""
    c = comp.reindex(index)
    b = binance.reindex(index)
    disp = 1e4 * np.log(b / c)
    f = pd.DataFrame(index=index)
    f["c_r1"] = np.log(c.shift(1) / c.shift(2)) / vol_prev
    f["c_r3"] = np.log(c.shift(1) / c.shift(4)) / (vol_prev * np.sqrt(3))
    f["c_disp"] = disp.shift(1) - disp.shift(2).rolling(60, min_periods=45).mean()
    return f.replace([np.inf, -np.inf], np.nan)


def label3(price: pd.Series, index: pd.DatetimeIndex) -> np.ndarray:
    """Signo(cierre de t + 3 − cierre de t): el blitz empieza con el clic (cierre de t) y dura 3 min."""
    d = price.reindex(index + pd.Timedelta(minutes=DUR)).to_numpy() - price.reindex(index).to_numpy()
    return np.where(np.isnan(d), np.nan, np.sign(np.where(np.abs(d) < 0.005, 0.0, d)))


def _walk_forward(X, y, ok, index, cfg, log) -> np.ndarray:
    st, ec = cfg["study"], cfg["execution"]
    label_end = pd.DatetimeIndex(index + pd.Timedelta(minutes=DUR + 2))
    p = np.full(len(index), np.nan)
    for fold in make_folds(TEST_START, TEST_END, 1, st["train_months"], st["calib_frac"]):
        fit, cal, test = fold.masks(index, label_end)
        valid = ok & ~np.isnan(y) & (y != 0)
        fit_nt, cal_nt, test_ok = fit & valid, cal & valid, test & ok
        _, (pc, pt) = fit_predict_proba("gbm", X[fit_nt], (y[fit_nt] == 1).astype(int), [X[cal_nt], X[test_ok]],
                                        seed=ec["seed"], max_rows=st["max_fit_rows"], features=list(X.columns))
        p[test_ok] = Calibrator().fit(pc, (y[cal_nt] == 1).astype(int)).transform(pt)
        log(f"  {fold.name}: ajuste={fit_nt.sum():,} calibración={cal_nt.sum():,} prueba={test_ok.sum():,}")
    return p


def run(root3: Path = Path("data/raw/estudio3"), daily: Path = Path("data/processed/senal/diario"),
        out_dir: Path = Path("results/estudio42"), n_boot: int = 1000, log=print) -> dict:
    cfg = load_config("config/research.toml")  # solo se lee
    margin = cfg["contracts"]["binary_ev_margin"]
    spot = pd.concat([load(root3, "BTCUSDT", "spot"), _read_days(Path(daily) / "1m", "2026-10-01", "2026-10-26")])
    spot = spot[~spot.index.duplicated(keep="last")].sort_index()
    bars = spot_bars(spot)
    data_start = pd.Timestamp(TEST_START, tz="UTC") - pd.DateOffset(months=12) - pd.Timedelta(days=7)
    bars = bars[(bars.index >= data_start) & (bars.index < pd.Timestamp(TEST_END, tz="UTC"))]
    idx = bars.index
    tab = build_table().reindex(idx)
    prev = compute_features(bars).shift(1)  # FEATURES de la vela t−1, ya cerrada en el segundo 50 de t
    vol_prev = np.exp(prev["lvol60"])
    cl = closes()
    comp = composite(cl)
    X = pd.concat([prev[FEATURES], partial_features(tab, bars["o"], vol_prev, K),
                   comp_features(comp, cl["binance"], vol_prev, idx)], axis=1)
    y = label3(comp, idx)
    y_bn = label3(cl["binance"], idx)
    tie = pd.Series(np.where(np.isnan(y), np.nan, (y == 0).astype(float)), index=idx)
    q_hat = tie.shift(DUR + 2).rolling(1440, min_periods=200).mean().to_numpy()
    ok = X.notna().all(axis=1).to_numpy() & ~np.isnan(q_hat)
    log("Modelo con la etiqueta del compuesto (el precio de IQ Option):")
    p = _walk_forward(X, y, ok, idx, cfg, log)
    log("Referencia: el mismo modelo con la etiqueta de Binance:")
    p_ref = _walk_forward(X, y_bn, ok, idx, cfg, log)
    contract = BinaryContract(PAYOUT, "refund")
    be = 1 / (1 + PAYOUT)
    sel = ~np.isnan(p)
    times = idx[sel]
    rep = {"estudio": "Estudio 42 — blitz de BTC de IQ Option con el precio compuesto (pre-registro 78891ce)",
           "git_sha": git_sha(), "periodo_prueba": [TEST_START, TEST_END], "pago": PAYOUT, "equilibrio": be,
           "hipotesis": {}, "informativo": {}}
    user_hours = (times.hour >= 2) & (times.hour < 6)  # 21:00–01:00 Bogotá
    for h, umbral in (("H42a", None), ("H42b", UMBRAL)):
        x = evaluate(p[sel], y[sel], q_hat[sel], times, contract, margin, n_boot, 1 - ALPHA, umbral=umbral)
        crit = {"min_300": x["operaciones"] >= 300, "p_bonferroni": x["p"] < ALPHA, "wilson": x["lo95"] > be,
                "ev_ic": x["ev_ic"][0] > 0, "meses_60": x["meses_ev_positivo"] >= 0.6}
        x.update({"criterios": crit, "pasa": all(crit.values())})
        rep["hipotesis"][h] = x
        # informativo: una a la vez, referencia con etiqueta de Binance y horario del usuario
        side = np.where(p[sel] >= 0.5, 1, -1)
        pmax = np.where(side == 1, p[sel], 1 - p[sel])
        take = (contract.ev(pmax, q_hat[sel]) >= margin) & ~np.isnan(y[sel]) & (pmax >= (umbral or 0))
        keep = np.zeros(len(take), bool)
        keep[np.flatnonzero(take)[one_at_a_time(times[take], DUR)]] = True
        info = {"una_a_la_vez": evaluate(np.where(keep, p[sel], 0.5), y[sel], q_hat[sel], times, contract, margin,
                                         200, 0.95, umbral=umbral),
                "referencia_binance": evaluate(p_ref[sel], y[sel], q_hat[sel], times, contract, margin, 200, 0.95,
                                               umbral=umbral),
                "horario_usuario": evaluate(np.where(user_hours, p[sel], 0.5), y[sel], q_hat[sel], times, contract,
                                            margin, 200, 0.95, umbral=umbral)}
        for d in info.values():
            d.pop("mensual")
        rep["informativo"][h] = info
        log(f"{h}: pasa={x['pasa']} | {x['operaciones']} ops, acierto {x['acierto']:.4f} [{x['lo95']:.4f}] "
            f"EV {x['ev']:+.4f} {x['ev_ic']} | {crit}")
        log("   " + " | ".join(f"{k}: {v['operaciones']} ops, {v['acierto'] and round(v['acierto'], 4)}"
                               for k, v in info.items()))
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"p": p[sel], "p_ref": p_ref[sel], "y": y[sel], "q": q_hat[sel]}, index=times).to_parquet(
        out_dir / "predicciones.parquet")
    (out_dir / "resultado.json").write_text(json.dumps(jsonable(rep), indent=2, ensure_ascii=False), encoding="utf-8")
    return rep
