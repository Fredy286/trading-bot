"""Estudio 17 (pre-registro en docs/01, commit 30503f6): Fibonacci («zona dorada») e ICT, desarmados.

Parte A: ¿la zona 50–61,8 % del retroceso es especial? En velas de 15 min de BTC, oro y EUR/USD, cada impulso del
zigzag causal (umbral 3·ATR14) da un evento por zona tocada (Z1 38,2–50 %, Z2 50–61,8 %, Z3 61,8–78,6 %). Se mide si
el precio llega antes al final del impulso (continuación) que a su inicio, frente a la referencia del azar 1 − r.

Parte B: ¿un bloque de 10 variables ICT/Fibonacci mejora el GBM de BTC a 1 min? Mismo diseño que el Estudio 15.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from ..data import store
from ..data.clean import to_canonical
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

ZONES = {"Z1": (0.382, 0.5), "Z2": (0.5, 0.618), "Z3": (0.618, 0.786)}
THR_ATR, MAX_BARS = 3.0, 200
ALPHA_A = 0.05 / 3
A_START, A_END = "2022-01-01", "2025-09-01"
B_TEST_START, B_TEST_END, B_DATA_START = "2024-07-01", "2025-09-01", "2023-06-01"
ICT_FEATURES = ["ict_sweep_hi", "ict_sweep_lo", "ict_bos", "ict_fvg", "ict_fvg15", "ict_pd", "ict_eqh", "ict_eql",
                "fib_r", "fib_gold"]


# ----------------------------------------------------------------------------------------------- zigzag causal
def _atr(h, l, c, n=14) -> np.ndarray:
    prev = np.r_[np.nan, c[:-1]]
    tr = np.nanmax(np.vstack([h - l, np.abs(h - prev), np.abs(l - prev)]), axis=0)
    tr[np.isnan(prev)] = np.nan
    return pd.Series(tr).rolling(n, min_periods=n).mean().to_numpy()


def zigzag(h: np.ndarray, l: np.ndarray, c: np.ndarray, thr: np.ndarray):
    """Impulsos confirmados sin mirar el futuro.

    Devuelve (impulsos, fib_r): impulsos = lista de (lado, inicio, fin, barra de confirmación); fib_r[t] = profundidad
    del retroceso del último impulso confirmado con velas hasta t (+ alcista, − bajista, 0 sin impulso).
    """
    n = len(c)
    fib = np.zeros(n)
    imps = []
    state = 0  # +1: último giro confirmado es un mínimo (se busca el máximo); −1: al revés
    ext_hi = ext_lo = np.nan  # extremos candidatos
    last_lo = last_hi = np.nan
    cur = None  # (lado, inicio, fin) del último impulso confirmado
    run_ext = np.nan  # extremo del retroceso actual
    for t in range(n):
        if np.isnan(c[t]) or np.isnan(thr[t]):
            continue
        if state == 0:
            ext_hi = np.nanmax([ext_hi, h[t]])
            ext_lo = np.nanmin([ext_lo, l[t]])
            if c[t] >= ext_lo + thr[t]:
                state, last_lo, ext_hi = 1, ext_lo, h[t]
            elif c[t] <= ext_hi - thr[t]:
                state, last_hi, ext_lo = -1, ext_hi, l[t]
            continue
        if state == 1:  # subiendo: se busca el máximo
            ext_hi = max(ext_hi, h[t])
            if c[t] <= ext_hi - thr[t]:
                imps.append((1, last_lo, ext_hi, t))
                cur, last_hi, state, ext_lo = (1, last_lo, ext_hi), ext_hi, -1, l[t]
                run_ext = l[t]
        else:  # bajando: se busca el mínimo
            ext_lo = min(ext_lo, l[t])
            if c[t] >= ext_lo + thr[t]:
                imps.append((-1, last_hi, ext_lo, t))
                cur, last_lo, state, ext_hi = (-1, last_hi, ext_lo), ext_lo, 1, h[t]
                run_ext = h[t]
        if cur is not None:
            side, a, b = cur
            if side == 1:
                run_ext = min(run_ext, l[t])
                fib[t] = (b - run_ext) / (b - a) if b > a else 0.0
            else:
                run_ext = max(run_ext, h[t])
                fib[t] = -(run_ext - b) / (a - b) if a > b else 0.0
    return imps, fib


def zone_events(h, l, imps, times) -> pd.DataFrame:
    """Primer toque de cada zona tras la confirmación del impulso y su resultado (fin antes que inicio)."""
    rows = []
    n = len(h)
    for side, a, b, tc in imps:
        size = abs(b - a)
        if size <= 0:
            continue
        deep = np.nan
        touched = set()
        for j in range(tc, min(n, tc + MAX_BARS)):
            if np.isnan(h[j]):
                continue
            if (side == 1 and (h[j] > b or l[j] <= a)) or (side == -1 and (l[j] < b or h[j] >= a)):
                break  # el retroceso terminó (nuevo extremo o vuelta al inicio)
            prev = deep
            r_j = (b - l[j]) / size if side == 1 else (h[j] - b) / size
            deep = r_j if np.isnan(deep) else max(deep, r_j)
            if j == tc:
                for z, (lo, _) in ZONES.items():
                    if deep >= lo:
                        touched.add(z)  # ya se había pasado al confirmar: no se puede operar
                continue
            for z, (lo, _) in ZONES.items():
                if z in touched or deep < lo or (not np.isnan(prev) and prev >= lo):
                    continue
                touched.add(z)
                rows.append({"zona": z, "r_e": lo, "t": j, "time": times[j], "lado": side,
                             "acierto": _outcome(h, l, side, a, b, j)})
    out = pd.DataFrame(rows, columns=["zona", "r_e", "t", "time", "lado", "acierto"])
    return out.dropna(subset=["acierto"])


def _outcome(h, l, side, a, b, j):
    for k in range(j + 1, min(len(h), j + 1 + MAX_BARS)):
        if np.isnan(h[k]):
            continue
        hit_end = h[k] >= b if side == 1 else l[k] <= b
        hit_start = l[k] <= a if side == 1 else h[k] >= a
        if hit_start:
            return 0.0  # si caen en la misma vela, cuenta fallo
        if hit_end:
            return 1.0
    return np.nan


def bars_15m(symbol: str, root3: Path, root: Path) -> pd.DataFrame:
    if symbol == "BTCUSDT":
        b1 = spot_bars(load(root3, symbol, "spot"))
    else:
        b1, _ = to_canonical(store.load(root, get_instrument(symbol), source="histdata"), fill_gaps=True)
    b1 = b1[(b1.index >= pd.Timestamp(A_START, tz="UTC") - pd.Timedelta(days=5)) &
            (b1.index < pd.Timestamp(A_END, tz="UTC"))]
    g = b1[["o", "h", "l", "c"]].resample("15min", label="left", closed="left")
    return pd.DataFrame({"o": g["o"].first(), "h": g["h"].max(), "l": g["l"].min(), "c": g["c"].last()}).dropna()


def part_a(symbol: str, root3: Path, root: Path, n_boot: int = 2000) -> dict:
    b = bars_15m(symbol, root3, root)
    h, l, c = (b[k].to_numpy() for k in ("h", "l", "c"))
    imps, _ = zigzag(h, l, c, THR_ATR * _atr(h, l, c))
    ev = zone_events(h, l, imps, b.index)
    ev = ev[ev["time"] >= pd.Timestamp(A_START, tz="UTC")]
    week = pd.DatetimeIndex(ev["time"]).strftime("%G-%V").to_numpy()
    uw, inv = np.unique(week, return_inverse=True)
    zone_codes = {z: (ev["zona"] == z).to_numpy() for z in ZONES}
    acc = ev["acierto"].to_numpy()
    base = {z: 1 - lo for z, (lo, _) in ZONES.items()}

    def stats(idx_weeks):
        ex = {}
        for z, m in zone_codes.items():
            s = np.bincount(inv, weights=acc * m, minlength=len(uw))[idx_weeks].sum()
            k = np.bincount(inv, weights=m.astype(float), minlength=len(uw))[idx_weeks].sum()
            ex[z] = s / k - base[z] if k else np.nan
        return ex

    point = stats(np.arange(len(uw)))
    rng = np.random.default_rng(12345)
    boots = [stats(rng.integers(0, len(uw), len(uw))) for _ in range(n_boot)]
    e2 = np.array([x["Z2"] for x in boots])
    dif = np.array([x["Z2"] - (x["Z1"] + x["Z3"]) / 2 for x in boots])
    q = [ALPHA_A / 2, 1 - ALPHA_A / 2]
    crit = {"exceso_dorada_positivo": bool(np.nanquantile(e2, q[0]) > 0),
            "dorada_mejor_que_vecinas": bool(np.nanquantile(dif, q[0]) > 0)}
    zonas = {z: {"eventos": int(m.sum()), "continuacion": float(acc[m].mean()) if m.any() else None,
                 "referencia_azar": base[z], "exceso": point[z]} for z, m in zone_codes.items()}
    return {"simbolo": symbol, "impulsos": len(imps), "zonas": zonas,
            "exceso_dorada_ic": [float(np.nanquantile(e2, q[0])), float(np.nanquantile(e2, q[1]))],
            "dorada_menos_vecinas": float(point["Z2"] - (point["Z1"] + point["Z3"]) / 2),
            "dorada_menos_vecinas_ic": [float(np.nanquantile(dif, q[0])), float(np.nanquantile(dif, q[1]))],
            "criterios": crit, "pasa": all(crit.values())}


# ----------------------------------------------------------------------------------------------- parte B
def ict_features(bars: pd.DataFrame, vol60: pd.Series) -> pd.DataFrame:
    """Bloque fijo del pre-registro (fila t = velas hasta el cierre de t)."""
    o, h, l, c = (bars[k] for k in ("o", "h", "l", "c"))
    f = pd.DataFrame(index=bars.index)
    hmax = h.shift(1).rolling(60, min_periods=60).max()
    lmin = l.shift(1).rolling(60, min_periods=60).min()
    f["ict_sweep_hi"] = ((h > hmax) & (c < hmax)).astype(float).where(hmax.notna())
    f["ict_sweep_lo"] = ((l < lmin) & (c > lmin)).astype(float).where(lmin.notna())
    f["ict_bos"] = np.where(c > hmax, 1.0, np.where(c < lmin, -1.0, 0.0))
    f.loc[hmax.isna(), "ict_bos"] = np.nan
    up_gap, dn_gap = l - h.shift(2), h - l.shift(2)
    scale = c * vol60
    f["ict_fvg"] = np.where(up_gap > 0, up_gap / scale, np.where(dn_gap < 0, dn_gap / scale, 0.0))
    fvg_sign = np.where(up_gap > 0, 1.0, np.where(dn_gap < 0, -1.0, 0.0))
    f["ict_fvg15"] = pd.Series(fvg_sign, index=bars.index).rolling(15, min_periods=15).sum()
    hi240, lo240 = h.rolling(240, min_periods=240).max(), l.rolling(240, min_periods=240).min()
    rng240 = hi240 - lo240
    f["ict_pd"] = ((c - lo240) / rng240.where(rng240 > 0)).where(rng240 > 0, 0.5).where(hi240.notna())
    tol = (0.1 * vol60 * c).to_numpy()
    for name, arr, sgn in (("ict_eqh", h.to_numpy(), 1), ("ict_eql", l.to_numpy(), -1)):
        out = np.full(len(arr), np.nan)
        win = np.lib.stride_tricks.sliding_window_view(arr, 59)  # ventana i = velas i … i+58
        for a in range(0, len(arr) - 59, 200_000):
            rows = np.arange(a + 59, min(len(arr), a + 59 + 200_000))
            w = win[rows - 59]  # velas t−59 … t−1
            ext = np.max(w, axis=1) if sgn == 1 else np.min(w, axis=1)
            dist = (ext[:, None] - w) if sgn == 1 else (w - ext[:, None])
            out[rows] = np.sum(dist <= tol[rows][:, None], axis=1) - 1
        f[name] = out
    hh, ll, cc = h.to_numpy(), l.to_numpy(), c.to_numpy()
    _, fib = zigzag(hh, ll, cc, THR_ATR * _atr(hh, ll, cc))
    f["fib_r"] = fib
    f["fib_gold"] = ((np.abs(fib) >= 0.5) & (np.abs(fib) <= 0.618)).astype(float)
    f.loc[c.isna()] = np.nan
    return f[ICT_FEATURES].replace([np.inf, -np.inf], np.nan)


def part_b(root3: Path, n_boot: int = 1000, log=print) -> dict:
    cfg = load_config("config/research.toml")  # solo se lee
    st, cc, ec = cfg["study"], cfg["contracts"], cfg["execution"]
    contract = BinaryContract(cc["binary_payout"], cc["binary_tie_rule"])
    bars = spot_bars(load(root3, "BTCUSDT", "spot"))
    bars = bars[(bars.index >= pd.Timestamp(B_DATA_START, tz="UTC")) & (bars.index < pd.Timestamp(B_TEST_END, tz="UTC"))]
    pf = compute_features(bars)
    nf = ict_features(bars, np.exp(pf["lvol60"]))
    lab = make_labels(bars, 1, 1, get_instrument("BTCUSDT").point)
    y = lab["dir"].to_numpy()
    tie = (lab["dir"] == 0).astype(float).where(lab["dir"].notna())
    q_hat = tie.shift(2).rolling(1440, min_periods=200).mean().to_numpy()
    ok = pf.notna().all(axis=1).to_numpy() & nf.notna().all(axis=1).to_numpy() & ~np.isnan(q_hat)
    X = {"referencia": pf[FEATURES], "prueba": pd.concat([pf[FEATURES], nf], axis=1)}
    label_end = pd.DatetimeIndex(lab["label_end"])
    p = {m: np.full(len(bars), np.nan) for m in X}
    for fold in make_folds(B_TEST_START, B_TEST_END, st["step_months"], st["train_months"], st["calib_frac"]):
        fit, cal, test = fold.masks(bars.index, label_end)
        valid = ok & ~np.isnan(y) & (y != 0)
        fit_nt, cal_nt, test_ok = fit & valid, cal & valid, test & ok & ~np.isnan(y)
        for m, Xm in X.items():
            _, (pc, pt) = fit_predict_proba("gbm", Xm[fit_nt], (y[fit_nt] == 1).astype(int), [Xm[cal_nt], Xm[test_ok]],
                                            seed=ec["seed"], max_rows=st["max_fit_rows"], features=list(Xm.columns))
            p[m][test_ok] = Calibrator().fit(pc, (y[cal_nt] == 1).astype(int)).transform(pt)
        log(f"[ICT] {fold.name}: ajuste={fit_nt.sum():,} prueba={test_ok.sum():,}")
    sel = ~np.isnan(p["referencia"])
    if np.allclose(p["referencia"][sel], p["prueba"][sel]):
        raise RuntimeError("Los dos modelos predicen igual: el bloque nuevo no llegó al ajuste (ítem 39).")
    times = bars.index[sel]

    def policy(pu):
        side = np.where(pu >= 0.5, 1, -1)
        take = contract.ev(np.where(side == 1, pu, 1 - pu), q_hat[sel]) >= cc["binary_ev_margin"]
        res = y[sel][take] * side[take]
        pnl = np.where(res == 0, 0.0, np.where(res > 0, contract.payout, -1.0))
        n, w = int((res != 0).sum()), int((res > 0).sum())
        lo, _ = wilson(w, n) if n else (float("nan"), 0)
        qs = pd.Series(pnl).groupby(pd.PeriodIndex(times[take].tz_convert(None), freq="Q")).sum()
        return {"operaciones": int(take.sum()), "acierto": w / n if n else None, "lo95": float(lo),
                "ev": float(pnl.mean()) if len(pnl) else None, "trimestres_ev_positivo": float((qs > 0).mean())}

    pol = {m: policy(p[m][sel]) for m in X}
    nt = y[sel] != 0
    yb = (y[sel][nt] == 1).astype(float)

    def ll(pp):
        pp = np.clip(pp, 1e-6, 1 - 1e-6)
        return -(yb * np.log(pp) + (1 - yb) * np.log(1 - pp))

    b = block_bootstrap_mean(ll(p["referencia"][sel][nt]) - ll(p["prueba"][sel][nt]),
                             times[nt].strftime("%Y-%m-%d"), n_boot=n_boot)
    t = pol["prueba"]
    crit = {"min_300": t["operaciones"] >= 300, "wilson": t["lo95"] > 1 / (1 + cc["binary_payout"]),
            "mejora_logloss": b["lo"] > 0, "ev_no_menor": (t["ev"] or -9) >= (pol["referencia"]["ev"] or -9),
            "trimestres_60": t["trimestres_ev_positivo"] >= 0.6}
    return {"politica_b": pol, "mejora_logloss": {"media": b["mean"], "ic95": [b["lo"], b["hi"]]},
            "criterios": crit, "pasa": all(crit.values())}


def run(root3: Path = Path("data/raw/estudio3"), root: Path = Path("data/raw"),
        out_dir: Path = Path("results/estudio17"), log=print) -> dict:
    a = {s: part_a(s, root3, root) for s in ("BTCUSDT", "XAUUSD", "EURUSD")}
    for s, r in a.items():
        log(f"[Fibonacci {s}] {r['zonas']} → pasa={r['pasa']}")
    b = part_b(root3, log=log)
    report = {"estudio": "Estudio 17 — Fibonacci e ICT (pre-registro 30503f6)", "git_sha": git_sha(),
              "parte_a_fibonacci": a, "parte_b_ict": b}
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "resultado.json").write_text(json.dumps(jsonable(report), indent=2, ensure_ascii=False),
                                            encoding="utf-8")
    return report
