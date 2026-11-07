"""Estudio 54 (pre-registro en docs/01): «event contracts» de OKX, «ETH/BTC Up or Down 5min».

Reglas del contrato (verificadas el 2026-11-07 con 6 contratos vencidos de ETH):
- precio de partida = índice de OKX (ETH-USDT o BTC-USDT) al comenzar la ventana;
- liquidación = media de los 30 cierres de 1 s del índice antes del vencimiento;
- sube si liquidación ≥ partida, baja si no;
- cada acción ganadora vale 1 USDT, menos la comisión de liquidación.

El aviso es anticipado: decisión en el segundo 50 del minuto anterior a la ventana (las ventanas empiezan en minutos
múltiplos de 5) con la receta del Estudio 42, y compra antes de que la ventana empiece.

Índice reconstruido al segundo: cierre de 1 s de Binance más la diferencia índice − Binance, interpolada entre
cierres de minuto (exacta en cada cierre).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import bolsas
from .calibration import Calibrator
from .experiment import git_sha, jsonable, load_config
from .features import FEATURES, compute_features
from .metrics import binom_pvalue_greater, block_bootstrap_mean, wilson
from .models import fit_predict_proba
from .study3 import load, spot_bars
from .study16 import partial_features
from .study20 import K, TEST_END, TEST_START, _read_days, build_table
from .study41 import composite
from .study42 import comp_features
from .study42 import closes as btc_closes
from .study47 import iq_at
from .walkforward import make_folds

ALPHA = 0.025
PRECIO, COMISION, MARGEN = 0.52, 0.02, 0.02  # compra antes de la ventana; comisión supuesta sobre el pago de 1 USDT
EQUILIBRIO = PRECIO / (1 - COMISION)
VENTANAS = {5: 30, 15: 60}  # duración (min) → segundos promediados en la liquidación
UMBRALES_INFO = (0.53, 0.55, 0.57, 0.60)
N_DAYS = 420
SIMBOLOS = {
    "ETHUSDT": {"indice": "ETH-USDT", "seg": (Path("data/processed/estudio26/ETHUSDT/1s"),), "hyp": "H54a"},
    "BTCUSDT": {"indice": "BTC-USDT", "seg": (Path("data/processed/estudio16/seg"), Path("data/processed/senal/seg")),
                "hyp": "H54b"},
}
SEC_DAILY_BTC = Path("data/processed/senal/diario/1s")


# ----------------------------------------------------------------------------------------------- etiquetas
def settle_labels(t: pd.DatetimeIndex, dur: int, idx_close: pd.Series, bn_close: pd.Series, si, sc) -> np.ndarray:
    """Resultado del contrato cuya ventana empieza en t + 1 min y dura `dur` min, decidido en la vela t:
    +1 si la media de los cierres de 1 s del índice en los últimos W s ≥ índice al empezar (cierre de la vela t);
    −1 si no. NaN si falta algún dato."""
    w = VENTANAS[dur]
    strike = idx_close.reindex(t).to_numpy()
    basis = (bn_close - idx_close).dropna()
    exp = (t + pd.Timedelta(minutes=1 + dur)).as_unit("ns").asi8
    inst = exp[:, None] - np.arange(w)[None, :] * 10**9  # instantes exp, exp − 1 s, …: cierres de los últimos W segundos
    vals = iq_at(pd.to_datetime(inst.ravel(), utc=True).to_numpy(), si, sc, basis).reshape(inst.shape)
    settle = vals.mean(axis=1)
    out = np.where(settle >= strike, 1.0, -1.0)
    return np.where(np.isnan(settle) | np.isnan(strike), np.nan, out)


def pnl(res: np.ndarray, precio: float = PRECIO, comision: float = COMISION) -> np.ndarray:
    """Ganancia por acción: acierto → 1 − comisión − precio; fallo → −precio."""
    return np.where(res > 0, 1 - comision - precio, -precio)


# ----------------------------------------------------------------------------------------------- datos
def _months(a: str = "2024-08", b: str = "2026-10") -> list[str]:
    return [p.strftime("%Y-%m") for p in pd.period_range(a, b, freq="M")]


def index_closes(indice: str) -> pd.Series:
    x = pd.concat([bolsas.okx_index_month(indice, m) for m in _months()]).sort_index()
    return x[~x.index.duplicated(keep="last")]


def sec_close(symbol: str, ym: str) -> pd.Series:
    for d in reversed(SIMBOLOS[symbol]["seg"]):
        f = d / f"{ym}.parquet"
        if f.exists():
            return pd.read_parquet(f, columns=["c"])["c"]
    if symbol == "BTCUSDT":
        days = sorted(SEC_DAILY_BTC.glob(f"{ym}-*.parquet"))
        if days:
            return pd.concat([pd.read_parquet(f, columns=["c"])["c"] for f in days]).sort_index()
    return pd.Series(dtype=float)


def inputs(symbol: str, root3: Path = Path("data/raw/estudio3"), daily: Path = Path("data/processed/senal/diario")):
    """Velas de 1 min de Binance, tabla del bloque parcial y cierres de 3 bolsas (las mismas fuentes del 42 y el 51)."""
    if symbol == "BTCUSDT":
        spot = pd.concat([load(root3, "BTCUSDT", "spot"), _read_days(Path(daily) / "1m", "2026-10-01", "2026-10-26")])
        tab = build_table()
        cl = btc_closes()
    else:
        from . import study51

        spot = study51.minute_bars(root3)
        tab = pd.read_parquet(study51.TAB)
        cl = {v: x for v, x in study51.closes().items() if v in ("binance", "bybit", "okx")}
    spot = spot[~spot.index.duplicated(keep="last")].sort_index()
    return spot_bars(spot), tab, cl


# ----------------------------------------------------------------------------------------------- modelo
def walk_forward(X: pd.DataFrame, y: np.ndarray, ok: np.ndarray, index: pd.DatetimeIndex, dur: int, cfg, log) -> np.ndarray:
    st, ec = cfg["study"], cfg["execution"]
    label_end = pd.DatetimeIndex(index + pd.Timedelta(minutes=dur + 3))  # purga: la etiqueta termina en t + 1 + dur
    valid = ok & ~np.isnan(y)
    p = np.full(len(index), np.nan)
    for fold in make_folds(TEST_START, TEST_END, 1, st["train_months"], st["calib_frac"]):
        fit, cal, test = fold.masks(index, label_end)
        fit_v, cal_v, test_ok = fit & valid, cal & valid, test & ok
        _, (pc, pt) = fit_predict_proba("gbm", X[fit_v], (y[fit_v] == 1).astype(int), [X[cal_v], X[test_ok]],
                                        seed=ec["seed"], max_rows=st["max_fit_rows"], features=list(X.columns))
        p[test_ok] = Calibrator().fit(pc, (y[cal_v] == 1).astype(int)).transform(pt)
        log(f"  {fold.name}: ajuste={fit_v.sum():,} calibración={cal_v.sum():,} prueba={test_ok.sum():,}")
    return p


def evaluate(p_up, y, times, umbral=None, precio=PRECIO, comision=COMISION, n_boot=1000, level=1 - ALPHA) -> dict:
    side = np.where(p_up >= 0.5, 1, -1)
    pdir = np.where(side == 1, p_up, 1 - p_up)
    take = (pdir * (1 - comision) - precio >= MARGEN) & ~np.isnan(y) & ~np.isnan(p_up)
    if umbral is not None:
        take &= pdir >= umbral
    res = (side * y)[take]
    g = pnl(res, precio, comision)
    n, w = int(len(res)), int((res > 0).sum())
    be = precio / (1 - comision)
    out = {"operaciones": n, "por_dia": n / N_DAYS, "acierto": w / n if n else None,
           "lo95": float(wilson(w, n)[0]) if n else float("nan"), "equilibrio": be,
           "p": binom_pvalue_greater(w, n, be) if n else 1.0}
    if n:
        tt = times[take]
        b = block_bootstrap_mean(g, tt.strftime("%G-%V"), n_boot=n_boot, level=level)
        month = pd.PeriodIndex(tt.tz_convert(None), freq="M").astype(str)
        mens = pd.Series(g).groupby(month).mean()
        out.update({"ev": b["mean"], "ev_ic": [b["lo"], b["hi"]], "roi": b["mean"] / precio,
                    "meses_ev_positivo": float((mens > 0).mean()), "mensual": {m: float(v) for m, v in mens.items()}})
    else:
        out.update({"ev": None, "ev_ic": [None, None], "roi": None, "meses_ev_positivo": 0.0, "mensual": {}})
    return out


def run_symbol(symbol: str, cfg, log=print, durs=(5, 15)) -> dict:
    meta = SIMBOLOS[symbol]
    bars, tab_all, cl = inputs(symbol)
    data_start = pd.Timestamp(TEST_START, tz="UTC") - pd.DateOffset(months=12) - pd.Timedelta(days=7)
    bars = bars[(bars.index >= data_start) & (bars.index < pd.Timestamp(TEST_END, tz="UTC"))]
    idx = bars.index
    tab = tab_all.reindex(idx)
    prev = compute_features(bars).shift(1)
    vol_prev = np.exp(prev["lvol60"])
    comp = composite(cl)
    X = pd.concat([prev[FEATURES], partial_features(tab, bars["o"], vol_prev, K),
                   comp_features(comp, cl["binance"], vol_prev, idx)], axis=1)
    ok = X.notna().all(axis=1).to_numpy()
    ix = index_closes(meta["indice"])
    labels = {d: np.full(len(idx), np.nan) for d in durs}
    months = _months(data_start.strftime("%Y-%m"), "2026-10")
    ym_arr = np.asarray(idx.strftime("%Y-%m"))
    for k, ym in enumerate(months):
        rows = np.flatnonzero(ym_arr == ym)
        if not len(rows):
            continue
        cur = sec_close(symbol, ym)
        nxt = sec_close(symbol, months[k + 1]).iloc[:3600] if k + 1 < len(months) else cur.iloc[:0]
        sec = pd.concat([cur, nxt]).sort_index()
        sec = sec[~sec.index.duplicated(keep="last")]
        if sec.empty:
            continue
        for d in durs:
            labels[d][rows] = settle_labels(idx[rows], d, ix, bars["c"], sec.index, sec.to_numpy(float))
        log(f"  {symbol} {ym}: {len(rows):,} minutos con etiqueta")
    out = {}
    for d in durs:
        log(f"Walk-forward {symbol}, contratos de {d} min:")
        p = walk_forward(X, labels[d], ok, idx, d, cfg, log)
        grid = ((idx.minute + 1) % d) == 0  # la ventana empieza en el minuto siguiente, múltiplo de d
        sel = ~np.isnan(p) & grid
        out[d] = {"p": p[sel], "y": labels[d][sel], "t": idx[sel]}
    return out


def run(out_dir: Path = Path("results/estudio54"), n_boot: int = 1000, log=print) -> dict:
    cfg = load_config("config/research.toml")  # solo se lee
    rep = {"estudio": "Estudio 54 — event contracts de OKX «Up or Down 5min» con aviso anticipado (pre-registro en docs/01)",
           "git_sha": git_sha(), "periodo_prueba": [TEST_START, TEST_END], "precio": PRECIO, "comision": COMISION,
           "equilibrio": EQUILIBRIO, "hipotesis": {}, "informativo": {}}
    preds = []
    for symbol, meta in SIMBOLOS.items():
        r = run_symbol(symbol, cfg, log)
        for d, x in r.items():
            ev = evaluate(x["p"], x["y"], x["t"], n_boot=n_boot)
            user = (x["t"].hour >= 2) & (x["t"].hour < 6)
            info = {"horario_usuario": evaluate(np.where(user, x["p"], 0.5), x["y"], x["t"], n_boot=200, level=0.95),
                    "precio_051_sin_comision": evaluate(x["p"], x["y"], x["t"], precio=0.51, comision=0.0, n_boot=200,
                                                        level=0.95),
                    "umbrales": {str(u): evaluate(x["p"], x["y"], x["t"], umbral=u, n_boot=200, level=0.95)
                                 for u in UMBRALES_INFO},
                    "tasa_sube": float(np.nanmean(x["y"] > 0))}
            for v in [info["horario_usuario"], info["precio_051_sin_comision"], *info["umbrales"].values()]:
                v.pop("mensual", None)
            if d == 5:
                crit = {"min_300": ev["operaciones"] >= 300, "p_bonferroni": ev["p"] < ALPHA,
                        "wilson": ev["lo95"] > EQUILIBRIO, "ev_ic": (ev["ev_ic"][0] or -1) > 0,
                        "meses_60": ev["meses_ev_positivo"] >= 0.6}
                ev.update({"criterios": crit, "pasa": all(crit.values())})
                rep["hipotesis"][meta["hyp"]] = {"simbolo": symbol, **ev}
                rep["informativo"][meta["hyp"]] = info
                log(f"{meta['hyp']} {symbol} 5 min: pasa={ev['pasa']} | {ev['operaciones']} ops ({ev['por_dia']:.1f}/día),"
                    f" acierto {ev['acierto']} [{ev['lo95']:.4f}] EV/acción {ev['ev']} | {crit}")
            else:
                ev.pop("mensual", None)
                rep["informativo"][f"{symbol}_{d}min"] = {**ev, **info}
                log(f"(informativo) {symbol} {d} min: {ev['operaciones']} ops, acierto {ev['acierto']}, EV {ev['ev']}")
            preds.append(pd.DataFrame({"simbolo": symbol, "dur": d, "p": x["p"], "y": x["y"]}, index=x["t"]))
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    pd.concat(preds).to_parquet(out_dir / "predicciones.parquet")
    (out_dir / "resultado.json").write_text(json.dumps(jsonable(rep), indent=2, ensure_ascii=False), encoding="utf-8")
    return rep
