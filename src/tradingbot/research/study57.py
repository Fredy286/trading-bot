"""Estudio 57 (pre-registro en docs/01, commit 8459934): huella en Binance de la manipulación del cierre de los
contratos «BTC Up or Down 5 min» de Polymarket (lanzados el 2026-02-12) y efecto en el GBM de BTC 1 min.

Diferencia en diferencias: (marcas de 5 min − otros minutos) DESPUÉS − lo mismo ANTES, con bootstrap de días UTC.
- H57a: cuota de volumen de los últimos 10 s antes del cambio de minuto (> 0).
- H57b: reversión del movimiento de los últimos 10 s en los 10 s siguientes (> 0).
- H57c: acierto del GBM del Estudio 48 (base) según si su entrada cae en una marca de 5 min (< 0).
Holm sobre las 3, α = 0,05 unilateral. Datos de Binance hasta 2026-09 (nada posterior al 2026-10-25).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from .experiment import git_sha, jsonable

WORK = Path("data/processed/estudio57")
FIRST_MONTH, LAST_MONTH = "2025-09", "2026-09"
START, LAUNCH, END = "2025-09-01", "2026-02-12", "2026-10-01"
PLACEBO = "2025-11-27"
ALPHA, N_BOOT, SEED = 0.05, 2000, 12345
MAX_GAP_S = 5
MIN_OPS_M5 = 1500
SIGNS = {"H57a": 1, "H57b": 1, "H57c": -1}  # dirección esperada de D


def boundary_table(sec: pd.DataFrame, minutes: pd.DatetimeIndex) -> pd.DataFrame:
    """Por cada cambio de minuto t: cuota de volumen de [t−10 s, t) sobre [t−60 s, t) y reversión de ±10 s.

    `sec` (velas de 1 s indexadas por su apertura, columnas c y v) debe cubrir de t − 60 s a t + 10 s.
    """
    start = minutes[0] - pd.Timedelta(seconds=60)
    grid = pd.date_range(start, minutes[-1] + pd.Timedelta(seconds=11), freq="s", tz="UTC", inclusive="left")
    s = sec.reindex(grid)
    present = s["c"].notna().to_numpy()
    pos = np.arange(len(grid))
    last_i = pd.Series(np.where(present, pos, np.nan)).ffill().to_numpy()
    c = s["c"].to_numpy()
    cv = np.r_[0.0, np.cumsum(s["v"].fillna(0.0).to_numpy(np.float64))]
    base = ((minutes - start) / pd.Timedelta(seconds=1)).to_numpy().astype(np.int64)

    def last_before(off: int) -> np.ndarray:
        """Último precio antes de t + off s (vela de 1 s que abre como mucho en t + off − 1), hueco ≤ 5 s."""
        j = base + off - 1
        li = last_i[j]
        ok = ~np.isnan(li) & (j - np.nan_to_num(li, nan=-1e9) <= MAX_GAP_S)
        return np.where(ok, c[np.nan_to_num(li, nan=0).astype(np.int64)], np.nan)

    p_m10, p0, p10 = last_before(-10), last_before(0), last_before(10)
    v10 = cv[base] - cv[base - 10]
    v60 = cv[base] - cv[base - 60]
    with np.errstate(invalid="ignore", divide="ignore"):
        share = np.where(v60 > 0, v10 / v60, np.nan)
        pre, post = np.log(p0 / p_m10), np.log(p10 / p0)
    rev = np.where((pre != 0) & (post != 0) & ~np.isnan(pre) & ~np.isnan(post),
                   -np.sign(pre) * np.sign(post), np.nan)
    return pd.DataFrame({"cuota": share, "reversion": rev}, index=minutes)


def build_table(work: Path = WORK) -> pd.DataFrame:
    files = sorted((Path(work) / "seg").glob("*.parquet"))
    parts = []
    for i, f in enumerate(files):
        sec = pd.read_parquet(f)
        if i + 1 < len(files):
            nxt = pd.read_parquet(files[i + 1])
            sec = pd.concat([sec, nxt[nxt.index < nxt.index[0].floor("min") + pd.Timedelta(minutes=2)]])
        m0 = pd.Timestamp(f.stem + "-01", tz="UTC") + pd.Timedelta(minutes=1)
        m1 = pd.Timestamp(f.stem + "-01", tz="UTC") + pd.offsets.MonthBegin(1)
        minutes = pd.date_range(m0, m1, freq="min", tz="UTC", inclusive="left")
        parts.append(boundary_table(sec, minutes))
        print(f"  tabla {f.stem}: {len(minutes):,} cambios de minuto", flush=True)
    t = pd.concat(parts)
    return t[~t.index.duplicated(keep="first")]


def is_m5(times: pd.DatetimeIndex) -> np.ndarray:
    return (times.minute % 5 == 0) & (times.second == 0)


def _day_sums(values: np.ndarray, group: np.ndarray, days: np.ndarray) -> pd.DataFrame:
    """Por día: suma y conteo de los valores válidos de cada grupo (1 = M5, 0 = O)."""
    ok = ~np.isnan(values)
    df = pd.DataFrame({"d": days[ok], "g": group[ok].astype(int), "v": values[ok]})
    agg = df.groupby(["d", "g"])["v"].agg(["sum", "count"]).unstack("g", fill_value=0)
    out = pd.DataFrame(index=agg.index)
    for g, name in ((1, "m5"), (0, "o")):
        out[f"s_{name}"] = agg[("sum", g)] if ("sum", g) in agg.columns else 0.0
        out[f"n_{name}"] = agg[("count", g)] if ("count", g) in agg.columns else 0
    return out


def _gap(sums: np.ndarray) -> float:
    """sums = [s_m5, n_m5, s_o, n_o] → media M5 − media O."""
    s_m, n_m, s_o, n_o = sums
    if n_m == 0 or n_o == 0:
        return float("nan")
    return s_m / n_m - s_o / n_o


def did(values: np.ndarray, times: pd.DatetimeIndex, group: np.ndarray, split: str, sign: int,
        start: str = START, end: str = END, n_boot: int = N_BOOT, seed: int = SEED) -> dict:
    """D = (M5 − O)_después − (M5 − O)_antes, con bootstrap de días dentro de cada periodo.

    p unilateral = (nº de D* en contra de `sign` + 1) / (n_boot + 1).
    """
    values = np.asarray(values, float)
    t0, t1, t2 = (pd.Timestamp(x, tz="UTC") for x in (start, split, end))
    inside = (times >= t0) & (times < t2)
    days = times.floor("D").to_numpy()
    per = {}
    for name, (a, b) in (("antes", (t0, t1)), ("despues", (t1, t2))):
        m = inside & (times >= a) & (times < b)
        per[name] = _day_sums(values[m], np.asarray(group)[m], days[m])[["s_m5", "n_m5", "s_o", "n_o"]].to_numpy(float)
    tot = {k: v.sum(0) for k, v in per.items()}
    d_hat = _gap(tot["despues"]) - _gap(tot["antes"])
    rng = np.random.default_rng(seed)
    boots = np.empty(n_boot)
    for i in range(n_boot):
        g = {}
        for k, arr in per.items():
            g[k] = _gap(arr[rng.integers(0, len(arr), len(arr))].sum(0)) if len(arr) else float("nan")
        boots[i] = g["despues"] - g["antes"]
    against = np.sum(boots <= 0) if sign > 0 else np.sum(boots >= 0)
    lo, hi = np.nanpercentile(boots, [2.5, 97.5]) if np.isfinite(boots).any() else (np.nan, np.nan)
    out = {"D": d_hat, "ic95": [float(lo), float(hi)], "p_unilateral": float((against + 1) / (n_boot + 1)),
           "dias": {k: int(len(v)) for k, v in per.items()}}
    for k, s in tot.items():
        out[k] = {"media_m5": s[0] / s[1] if s[1] else None, "n_m5": int(s[1]),
                  "media_o": s[2] / s[3] if s[3] else None, "n_o": int(s[3])}
    return out


def holm(pvals: dict[str, float], alpha: float = ALPHA) -> dict[str, dict]:
    order = sorted(pvals, key=lambda k: pvals[k])
    m, out, running, stop = len(order), {}, 0.0, False
    for i, k in enumerate(order):
        adj = min(1.0, (m - i) * pvals[k])
        running = max(running, adj)
        rejected = (not stop) and running < alpha
        stop = stop or not rejected
        out[k] = {"p": pvals[k], "p_holm": running, "pasa": bool(rejected)}
    return out


def monthly_gap(values: np.ndarray, times: pd.DatetimeIndex, group: np.ndarray) -> dict:
    df = pd.DataFrame({"v": values, "g": np.asarray(group, int), "m": times.strftime("%Y-%m")}).dropna()
    piv = df.groupby(["m", "g"])["v"].mean().unstack("g")
    return {m: float(r.get(1, np.nan) - r.get(0, np.nan)) for m, r in piv.iterrows()}


def gbm_trades(root3: Path, log=print, download: bool = True) -> pd.DataFrame:
    """Operaciones de la política base del GBM del Estudio 48 en la verificación (2025-09 → 2026-09)."""
    from ..instruments import get_instrument
    from .contracts import BinaryContract
    from .experiment import load_config
    from .features import FEATURES, compute_features
    from .labels import make_labels
    from .study3 import download as dl
    from .study3 import load, spot_bars
    from .study33 import _predict
    from .study48 import DATA_END, DATA_START, SYMBOL

    if download:
        dl(root3, "2020-12", "2026-09", symbols=(SYMBOL,), kinds=("spot",))
    cfg = load_config("config/research.toml")  # solo se lee
    st, cc, ec = cfg["study"], cfg["contracts"], cfg["execution"]
    contract = BinaryContract(cc["binary_payout"], cc["binary_tie_rule"])
    bars = spot_bars(load(root3, SYMBOL, "spot"))
    bars = bars[(bars.index >= pd.Timestamp(DATA_START, tz="UTC")) & (bars.index < pd.Timestamp(DATA_END, tz="UTC"))]
    idx = bars.index
    X = compute_features(bars)[FEATURES]
    lab = make_labels(bars, 1, 1, get_instrument(SYMBOL).point)
    y = lab["dir"].to_numpy()
    tie = (lab["dir"] == 0).astype(float).where(lab["dir"].notna())
    q_hat = tie.shift(2).rolling(1440, min_periods=200).mean().to_numpy()
    ok = X.notna().all(axis=1).to_numpy()
    p = _predict(X, y, ok, idx, pd.DatetimeIndex(lab["label_end"]), START, END, st, ec, log, "verificacion")
    side = np.where(p >= 0.5, 1, -1)
    p_dir = np.where(side == 1, p, 1 - p)
    sel = ~np.isnan(p) & ~np.isnan(y) & ~np.isnan(q_hat)
    take = sel & (contract.ev(p_dir, np.nan_to_num(q_hat)) >= cc["binary_ev_margin"])
    entry = idx[take] + pd.Timedelta(minutes=1)  # entrada en la apertura de la vela siguiente
    return pd.DataFrame({"res": (y[take] * side[take]).astype(float)}, index=entry)


def trade_stats(res: np.ndarray, payout: float = 0.85) -> dict:
    dec = res[res != 0]
    if len(dec) == 0:
        return {"operaciones": int(len(res)), "acierto": None, "ev": None}
    w = float(np.mean(dec == 1))
    ev = float(np.mean(np.where(res == 1, payout, np.where(res == -1, -1.0, 0.0))))
    return {"operaciones": int(len(res)), "acierto": w, "ev": ev}


def run(root3: Path = Path("data/raw/estudio3"), work: Path = WORK, out_dir: Path = Path("results/estudio57"),
        n_boot: int = N_BOOT, log=print, download: bool = True, trades: pd.DataFrame | None = None) -> dict:
    if download:
        from .study16 import download as dl_sec
        dl_sec("BTCUSDT", work, FIRST_MONTH, LAST_MONTH)
    tab = build_table(work)
    tab = tab[(tab.index >= pd.Timestamp(START, tz="UTC")) & (tab.index < pd.Timestamp(END, tz="UTC"))]
    t = tab.index
    g = is_m5(t)
    q15 = (t.minute % 15 == 0)
    rep = {"estudio": "Estudio 57 — huella de la manipulación del cierre de 5 min de Polymarket (pre-registro 8459934)",
           "git_sha": git_sha(), "periodos": {"antes": [START, LAUNCH], "despues": [LAUNCH, END]},
           "hipotesis": {}, "informativo": {}}
    for h, col in (("H57a", "cuota"), ("H57b", "reversion")):
        v = tab[col].to_numpy()
        rep["hipotesis"][h] = did(v, t, g, LAUNCH, SIGNS[h], START, END, n_boot=n_boot)
        rep["informativo"][f"{h}_mes_a_mes_M5_menos_O"] = monthly_gap(v, t, g)
        rep["informativo"][f"{h}_placebo_{PLACEBO}"] = did(v, t, g, PLACEBO, SIGNS[h], START, LAUNCH, n_boot=n_boot)
        m = g  # solo minutos M5: cuartos de hora frente a las demás M5
        rep["informativo"][f"{h}_cuartos_frente_a_otras_M5"] = did(v[m], t[m], q15[m], LAUNCH, SIGNS[h],
                                                                   START, END, n_boot=n_boot)
        log(f"{h}: D = {rep['hipotesis'][h]['D']:+.5f}  p = {rep['hipotesis'][h]['p_unilateral']:.4f}")
    if trades is None:
        trades = gbm_trades(root3, log, download)
    te = pd.DatetimeIndex(trades.index)
    res = trades["res"].to_numpy()
    win = np.where(res == 0, np.nan, (res == 1).astype(float))
    gm = is_m5(te)
    rep["hipotesis"]["H57c"] = did(win, te, gm, LAUNCH, SIGNS["H57c"], START, END, n_boot=n_boot)
    launch = pd.Timestamp(LAUNCH, tz="UTC")
    tabla = {}
    for per, msk in (("antes", te < launch), ("despues", te >= launch)):
        for nombre, gg in (("M5", gm), ("O", ~gm)):
            tabla[f"{per}_{nombre}"] = trade_stats(res[msk & gg])
    rep["informativo"]["H57c_operaciones"] = tabla
    rep["informativo"]["H57c_placebo_" + PLACEBO] = did(win, te, gm, PLACEBO, SIGNS["H57c"], START, LAUNCH,
                                                        n_boot=n_boot)
    q15t = (te.minute % 15 == 0)
    rep["informativo"]["H57c_cuartos_frente_a_otras_M5"] = did(win[gm], te[gm], q15t[gm], LAUNCH, SIGNS["H57c"],
                                                               START, END, n_boot=n_boot)
    log(f"H57c: D = {rep['hipotesis']['H57c']['D']:+.5f}  p = {rep['hipotesis']['H57c']['p_unilateral']:.4f}")
    adj = holm({h: rep["hipotesis"][h]["p_unilateral"] for h in SIGNS})
    for h in SIGNS:
        rep["hipotesis"][h].update(adj[h])
    potencia = all(tabla[f"{p}_M5"]["operaciones"] >= MIN_OPS_M5 for p in ("antes", "despues"))
    rep["hipotesis"]["H57c"]["potencia_minima"] = potencia
    rep["hipotesis"]["H57c"]["pasa"] = bool(rep["hipotesis"]["H57c"]["pasa"] and potencia)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "resultado.json").write_text(json.dumps(jsonable(rep), indent=2, ensure_ascii=False), encoding="utf-8")
    return rep
