"""Estudio 20 (pre-registro en docs/01, commit c53c0b2): repetición mes a mes del modelo H16b, 2025-09 → 2026-10-25.

Cada mes M se predice con un GBM entrenado SOLO con los 12 meses anteriores al inicio de M (último 20 % para calibrar,
con purga). H20a: contrato de 1 min en todas las velas, pago 85 %. H20b: solo las velas que dejan el vencimiento en un
cuarto de hora (binaria de 15 min de la plataforma del usuario), pago 87 %. No mira datos posteriores al 2026-10-25.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from ..live.anticipada import _training_table
from .calibration import Calibrator
from .contracts import BinaryContract
from .experiment import git_sha, jsonable, load_config
from .features import FEATURES, compute_features
from .metrics import binom_pvalue_greater, block_bootstrap_mean, wilson
from .models import fit_predict_proba
from .study3 import load, spot_bars
from .study16 import label, partial_features
from .study19 import quarter_aligned
from .walkforward import make_folds

K, LAT, LATENCIES = 50, 10, (0, 5, 10, 15)
TEST_START, TEST_END, DATA_START = "2025-09-01", "2026-10-26", "2024-08-25"
ALPHA = 0.05 / 2
UMBRALES = (0.56, 0.58, 0.60, 0.62)
HYPS = {"H20a": (0.85, False), "H20b": (0.87, True)}
WORK = Path("data/processed/estudio20")


def _read_days(folder: Path, start: str, end: str) -> pd.DataFrame:
    days = pd.date_range(start, end, freq="D", inclusive="left")
    return pd.concat([pd.read_parquet(Path(folder) / f"{d:%Y-%m-%d}.parquet") for d in days]).sort_index()


def build_table(sec_old: Path = Path("data/processed/estudio16/tabla_minutos.parquet"),
                sec_monthly: Path = Path("data/processed/senal/seg"),
                daily: Path = Path("data/processed/senal/diario"), work: Path = WORK) -> pd.DataFrame:
    """Tabla de minutos del Estudio 16 (hasta 2025-08) + la misma tabla para 2025-09 → 2026-10-25."""
    f = Path(work) / "tabla_minutos_2025_09.parquet"
    if not f.exists():
        sec_oct = _read_days(Path(daily) / "1s", "2026-10-01", "2026-10-26")
        minutes = pd.date_range("2025-09-01", "2026-10-26", freq="min", tz="UTC", inclusive="left")
        Path(work).mkdir(parents=True, exist_ok=True)
        _training_table(sec_monthly, sec_oct, minutes).to_parquet(f)
    old = pd.read_parquet(sec_old)
    new = pd.read_parquet(f)
    tab = pd.concat([old[old.index < pd.Timestamp(TEST_START, tz="UTC")], new])
    return tab[~tab.index.duplicated(keep="last")].sort_index()


def evaluate(p_up, d, q, times, contract, margin, n_boot, level, umbral=None) -> dict:
    side = np.where(p_up >= 0.5, 1, -1)
    pmax = np.where(side == 1, p_up, 1 - p_up)
    take = (contract.ev(pmax, q) >= margin) & ~np.isnan(d)
    if umbral is not None:
        take &= pmax >= umbral
    res = d[take] * side[take]
    pnl = np.where(res == 0, 0.0, np.where(res > 0, contract.payout, -1.0))
    n, w = int((res != 0).sum()), int((res > 0).sum())
    lo, _ = wilson(w, n) if n else (float("nan"), 0)
    tt = times[take]
    b = block_bootstrap_mean(pnl, tt.strftime("%G-%V"), n_boot=n_boot, level=level)
    month = pd.PeriodIndex(tt.tz_convert(None), freq="M").astype(str)
    df = pd.DataFrame({"m": month, "pnl": pnl, "win": res > 0, "dec": res != 0})
    g = df.groupby("m")
    mensual = {m: {"operaciones": int(len(x)), "acierto": float(x["win"].sum() / max(x["dec"].sum(), 1)),
                   "ev": float(x["pnl"].mean())} for m, x in g}
    days = max(len(set(tt.strftime("%Y-%m-%d"))), 1)
    return {"operaciones": int(take.sum()), "por_dia": int(take.sum()) / days, "acierto": w / n if n else None,
            "lo95": float(lo), "p": binom_pvalue_greater(w, n, 1 / (1 + contract.payout)) if n else 1.0,
            "ev": b["mean"], "ev_ic": [b["lo"], b["hi"]],
            "meses_ev_positivo": float(np.mean([v["ev"] > 0 for v in mensual.values()])) if mensual else 0.0,
            "mensual": mensual}


def run(root3: Path = Path("data/raw/estudio3"), daily: Path = Path("data/processed/senal/diario"),
        out_dir: Path = Path("results/estudio20"), n_boot: int = 1000, log=print) -> dict:
    cfg = load_config("config/research.toml")  # solo se lee
    st, cc, ec = cfg["study"], cfg["contracts"], cfg["execution"]
    margin = cc["binary_ev_margin"]
    spot = pd.concat([load(root3, "BTCUSDT", "spot"), _read_days(Path(daily) / "1m", "2026-10-01", "2026-10-26")])
    spot = spot[~spot.index.duplicated(keep="last")].sort_index()
    bars = spot_bars(spot)
    bars = bars[(bars.index >= pd.Timestamp(DATA_START, tz="UTC")) & (bars.index < pd.Timestamp(TEST_END, tz="UTC"))]
    tab = build_table().reindex(bars.index)
    prev = compute_features(bars).shift(1)  # FEATURES de la vela t−1, ya cerrada en el segundo k de t
    X = pd.concat([prev[FEATURES], partial_features(tab, bars["o"], np.exp(prev["lvol60"]), K)], axis=1)
    y = label(tab, K, LAT)
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
        log(f"{fold.name}: ajuste={fit_nt.sum():,} calibración={cal_nt.sum():,} prueba={test_ok.sum():,}")
    report = {"estudio": "Estudio 20 — repetición mes a mes (pre-registro c53c0b2)", "git_sha": git_sha(),
              "periodo_prueba": [TEST_START, "2026-10-25"], "hipotesis": {}}
    for hname, (payout, quarter) in HYPS.items():
        contract = BinaryContract(payout, "refund")
        sel = ~np.isnan(p) & (quarter_aligned(bars.index, 1) if quarter else True)
        times = bars.index[sel]
        args = (p[sel], y[sel], q_hat[sel], times, contract, margin)
        main = evaluate(*args, n_boot, 1 - ALPHA)
        be = 1 / (1 + payout)
        crit = {"min_300": main["operaciones"] >= 300, "p_bonferroni": main["p"] < ALPHA, "wilson": main["lo95"] > be,
                "ev_ic": main["ev_ic"][0] > 0, "meses_60": main["meses_ev_positivo"] >= 0.6}
        sens = {f"L={L}s": evaluate(p[sel], label(tab, K, L)[sel], q_hat[sel], times, contract, margin, 200, 0.95)
                for L in LATENCIES}
        selec = {f"p>={u}": evaluate(*args, 200, 0.95, umbral=u) for u in UMBRALES}
        for d in list(sens.values()) + list(selec.values()):
            d.pop("mensual")
        report["hipotesis"][hname] = {"pago": payout, "equilibrio": be, "cuarto_de_hora": quarter, **main,
                                      "criterios": crit, "pasa": all(crit.values()),
                                      "sensibilidad_latencia": sens, "selectividad": selec}
        log(f"{hname}: pasa={all(crit.values())} | n={main['operaciones']} acierto={main['acierto']:.4f} "
            f"EV={main['ev']:+.4f} {main['ev_ic']}")
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "resultado.json").write_text(json.dumps(jsonable(report), indent=2, ensure_ascii=False),
                                            encoding="utf-8")
    return report
