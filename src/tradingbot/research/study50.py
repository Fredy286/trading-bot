"""Estudio 50 (pre-registro en docs/01): «blitz continuo». El modelo del blitz de BTC de IQ Option (3 min desde la
compra, pago 86 %) decide cada 10 s y no solo en el segundo 50 de cada minuto.

- Variables: las 27 `FEATURES` de la vela de 1 min anterior de Binance y las 3 del compuesto (Estudio 42), más 21
  variables «deslizantes» medidas con las velas de 1 s de Binance cerradas antes del instante de decisión.
- Etiqueta de entrenamiento: compuesto de 3 bolsas (Estudio 42), reconstruido al segundo.
- Juicio: precio de IQ reconstruido al segundo (pesos del Estudio 47). El clic llega a +10 s y vence 180 s después.
- Referencia: el blitz actual (predicciones del Estudio 42, una decisión por minuto) juzgado igual.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from .calibration import Calibrator
from .contracts import BinaryContract
from .experiment import git_sha, jsonable, load_config
from .features import FEATURES, compute_features
from .metrics import binom_pvalue_greater, block_bootstrap_mean, wilson
from .models import fit_predict_proba
from .study3 import load, spot_bars
from .study20 import TEST_END, TEST_START, _read_days
from .study41 import composite
from .study42 import COMP, closes, comp_features
from .study47 import PRED, WEIGHTS, _ns, gate_month, iq_at, iq_price
from .walkforward import make_folds

GRID_S, DELAY_S, DUR_S, COOLDOWN_S = 10, 10, 180, 60
PAYOUT, ALPHA, MIN_RATIO, MARGIN = 0.86, 0.025, 1.5, 0.02
HYPS = {"H50a": (0.57, 0.560), "H50b": (0.60, 0.580)}  # (umbral, acierto mínimo)
UMBRALES_INFO = (0.55, 0.56, 0.57, 0.58, 0.59, 0.60, 0.61, 0.62)
DEMORAS_INFO = (20, 30)
R_WIN = (5, 10, 20, 30, 60, 120, 180, 300)
POS_WIN = (30, 60, 180, 300)
RNG_WIN = (60, 300)
TIB_WIN = (10, 30, 60, 300)
SLIDE = ([f"s_r{k}" for k in R_WIN] + [f"s_pos{w}" for w in POS_WIN] + [f"s_rng{w}" for w in RNG_WIN]
         + [f"s_tib{w}" for w in TIB_WIN] + ["s_vrel60", "s_rv300", "s_sec"])
COLS = list(FEATURES) + list(COMP) + SLIDE
MAX_MISSING = 10  # de las últimas 60 velas de 1 s
HIST_S = 3600     # historia de 1 s necesaria antes de cada decisión
SEC_DIRS = (Path("data/processed/estudio16/seg"), Path("data/processed/senal/seg"))
SEC_DAILY = Path("data/processed/senal/diario/1s")
N_DAYS = 420  # 2025-09-01 → 2026-10-25, ambos incluidos


# ----------------------------------------------------------------------------------------------- variables
def sliding_block(sec: pd.DataFrame, t: pd.DatetimeIndex, vol: np.ndarray) -> pd.DataFrame:
    """21 variables deslizantes en los instantes `t` con las velas de 1 s (`h`, `l`, `c`, `v`, `tb`; índice =
    apertura) CERRADAS antes de t (abiertas en t − 1 s o antes). `vol`: volatilidad por minuto (exp(lvol60) de la
    vela de 1 min anterior), una por instante."""
    sec = sec[~sec.index.duplicated(keep="last")].sort_index()
    t = pd.DatetimeIndex(t)
    out = pd.DataFrame(np.nan, index=t, columns=SLIDE, dtype=np.float64)
    if sec.empty or not len(t):
        return out
    start = sec.index[0]
    grid = pd.date_range(start, sec.index[-1], freq="s")
    s = sec.reindex(grid)
    present = s["c"].notna().to_numpy()
    c = s["c"].ffill().to_numpy(np.float64)
    h = np.where(present, s["h"].to_numpy(np.float64), c)
    lo = np.where(present, s["l"].to_numpy(np.float64), c)
    v = s["v"].fillna(0.0).to_numpy(np.float64)
    tb = s["tb"].fillna(0.0).to_numpy(np.float64)
    j = (_ns(t) - 10**9 - _ns(pd.DatetimeIndex([start]))[0]) // 10**9  # última vela cerrada antes de t
    ok = (j >= HIST_S) & (j < len(grid))
    j = np.where(ok, j, HIST_S).astype(np.int64)
    vol = np.asarray(vol, np.float64)
    logc = np.log(c)
    for k in R_WIN:
        out[f"s_r{k}"] = (logc[j] - logc[j - k]) / (vol * np.sqrt(k / 60))
    hs, ls = pd.Series(h), pd.Series(lo)
    for w in sorted(set(POS_WIN) | set(RNG_WIN)):
        mx = hs.rolling(w).max().to_numpy()[j]
        mn = ls.rolling(w).min().to_numpy()[j]
        rng = mx - mn
        if w in POS_WIN:
            out[f"s_pos{w}"] = np.where(rng > 0, (c[j] - mn) / np.where(rng > 0, rng, 1.0), 0.5)
        if w in RNG_WIN:
            out[f"s_rng{w}"] = (np.log(mx) - np.log(mn)) / (vol * np.sqrt(w / 60))
    cv = np.concatenate([[0.0], np.cumsum(v)])  # cv[i + 1] = suma de v[0..i]
    ctb = np.concatenate([[0.0], np.cumsum(tb)])

    def wsum(cs, w):  # suma de las últimas w velas que terminan en j (incluida)
        return cs[j + 1] - cs[j + 1 - w]

    for w in TIB_WIN:
        vw, bw = wsum(cv, w), wsum(ctb, w)
        out[f"s_tib{w}"] = np.where(vw > 0, 2 * bw / np.where(vw > 0, vw, 1.0) - 1, 0.0)
    v60, v3600 = wsum(cv, 60), wsum(cv, 3600)
    out["s_vrel60"] = np.log((v60 + 1e-9) / (v3600 / 60 + 1e-9))
    r1 = np.concatenate([[np.nan], np.diff(logc)])
    sd = pd.Series(r1).rolling(300, min_periods=250).std().to_numpy()[j]
    with np.errstate(divide="ignore", invalid="ignore"):
        out["s_rv300"] = np.log(sd * np.sqrt(60) / vol)
    out["s_sec"] = t.second.to_numpy().astype(float)
    cp = np.concatenate([[0], np.cumsum(~present)])
    miss = cp[j + 1] - cp[j + 1 - 60]
    bad = ~ok | (miss > MAX_MISSING) | ~np.isfinite(vol) | (vol <= 0)
    out.loc[bad, :] = np.nan
    return out.replace([np.inf, -np.inf], np.nan)


def minute_block(bars: pd.DataFrame, cl: dict[str, pd.Series]) -> pd.DataFrame:
    """FEATURES de la vela de 1 min anterior y variables del compuesto (Estudio 42), indexadas por la vela en curso."""
    prev = compute_features(bars).shift(1)
    vol_prev = np.exp(prev["lvol60"])
    comp = composite({v: cl[v] for v in ("binance", "bybit", "okx")})
    cf = comp_features(comp, cl["binance"], vol_prev, bars.index)
    out = pd.concat([prev[FEATURES], cf[COMP]], axis=1)
    out["vol"] = vol_prev
    return out


# ----------------------------------------------------------------------------------------------- etiquetas
def outcome(t_in: np.ndarray, t_out: np.ndarray, si, sc, basis: pd.Series | None) -> np.ndarray:
    """Signo(precio(t_out) − precio(t_in)) con el precio reconstruido al segundo; `basis=None` → Binance solo."""
    if basis is None:
        from .study47 import last_before
        a, b = last_before(si, sc, t_in), last_before(si, sc, t_out)
    else:
        a, b = iq_at(t_in, si, sc, basis), iq_at(t_out, si, sc, basis)
    d = b - a
    return np.where(np.isnan(d), np.nan, np.sign(np.where(np.abs(d) < 0.005, 0.0, d)))


# ----------------------------------------------------------------------------------------------- política
def coprime_step(n: int, max_rows: int) -> int:
    """Paso de la submuestra regular, primo relativo con 6 (las 6 decisiones de cada minuto entran)."""
    step = max(1, math.ceil(n / max_rows))
    while math.gcd(step, 6) != 1:
        step += 1
    return step


def take_signals(times: pd.DatetimeIndex, p_up: np.ndarray, valid: np.ndarray, umbral: float,
                 cooldown_s: int = COOLDOWN_S, q: np.ndarray | float = 0.0) -> tuple[np.ndarray, np.ndarray]:
    """Filas con señal (p de la dirección ≥ umbral y EV ≥ 0,02) dejando `cooldown_s` s tras cada señal."""
    p_up = np.asarray(p_up, float)
    side = np.where(p_up >= 0.5, 1, -1)
    pdir = np.where(side == 1, p_up, 1 - p_up)
    ev = BinaryContract(PAYOUT, "refund").ev(pdir, np.broadcast_to(np.asarray(q, float), pdir.shape))
    cand = np.flatnonzero((pdir >= umbral) & (ev >= MARGIN) & valid & ~np.isnan(p_up))
    if cooldown_s <= 0 or not len(cand):
        return cand, side
    ts = _ns(times[cand]) // 10**9
    keep, last = [], -10**18
    for i, s in zip(cand.tolist(), ts.tolist()):
        if s - last >= cooldown_s:
            keep.append(i)
            last = s
    return np.asarray(keep, dtype=np.int64), side


def summarize(times: pd.DatetimeIndex, res: np.ndarray, n_boot: int = 1000, level: float = 1 - ALPHA,
              n_days: int = N_DAYS) -> dict:
    """res = lado × resultado (+1 acierto, −1 fallo, 0 empate) de las operaciones tomadas."""
    res = np.asarray(res, float)
    be = 1 / (1 + PAYOUT)
    pnl = np.where(res == 0, 0.0, np.where(res > 0, PAYOUT, -1.0))
    n, w = int((res != 0).sum()), int((res > 0).sum())
    lo = wilson(w, n)[0] if n else float("nan")
    out = {"operaciones": int(len(res)), "por_dia": len(res) / n_days, "acierto": w / n if n else None,
           "lo95": float(lo), "p": binom_pvalue_greater(w, n, be) if n else 1.0}
    if len(res):
        b = block_bootstrap_mean(pnl, pd.DatetimeIndex(times).strftime("%G-%V"), n_boot=n_boot, level=level)
        month = pd.PeriodIndex(pd.DatetimeIndex(times).tz_convert(None), freq="M").astype(str)
        g = pd.DataFrame({"m": month, "pnl": pnl}).groupby("m")["pnl"]
        mensual = {m: {"operaciones": int(len(x)), "ev": float(x.mean())} for m, x in g}
        out.update({"ev": b["mean"], "ev_ic": [b["lo"], b["hi"]], "ganancia_por_dia": float(pnl.sum()) / n_days,
                    "meses_ev_positivo": float(np.mean([x["ev"] > 0 for x in mensual.values()])),
                    "mensual": mensual})
    else:
        out.update({"ev": None, "ev_ic": [None, None], "ganancia_por_dia": 0.0, "meses_ev_positivo": 0.0,
                    "mensual": {}})
    return out


# ----------------------------------------------------------------------------------------------- datos
def sec_month(ym: str) -> pd.DataFrame:
    """Velas de 1 s de BTCUSDT de Binance de un mes (h, l, c, v, tb)."""
    for d in reversed(SEC_DIRS):
        f = d / f"{ym}.parquet"
        if f.exists():
            return pd.read_parquet(f, columns=["h", "l", "c", "v", "tb"])
    days = sorted(SEC_DAILY.glob(f"{ym}-*.parquet"))
    if not days:
        return pd.DataFrame(columns=["h", "l", "c", "v", "tb"])
    return pd.concat([pd.read_parquet(f, columns=["h", "l", "c", "v", "tb"]) for f in days]).sort_index()


def _months(a: pd.Timestamp, b: pd.Timestamp) -> list[str]:
    return [p.strftime("%Y-%m") for p in pd.period_range(a.tz_convert(None), b.tz_convert(None), freq="M")]


# ----------------------------------------------------------------------------------------------- estudio
def build(root3: Path = Path("data/raw/estudio3"), daily: Path = Path("data/processed/senal/diario"), log=print):
    """Matriz de variables en la rejilla de 10 s y etiquetas (entrenamiento, juicio, informativas)."""
    test_start, test_end = pd.Timestamp(TEST_START, tz="UTC"), pd.Timestamp(TEST_END, tz="UTC")
    data_start = test_start - pd.DateOffset(months=12) - pd.Timedelta(days=7)
    spot = pd.concat([load(root3, "BTCUSDT", "spot"), _read_days(Path(daily) / "1m", "2026-10-01", "2026-10-26")])
    spot = spot[~spot.index.duplicated(keep="last")].sort_index()
    bars = spot_bars(spot)
    bars = bars[(bars.index >= data_start - pd.Timedelta(days=2)) & (bars.index < test_end)]
    cl = closes()
    cl["gate"] = pd.concat([gate_month(m) for m in _months(test_start, test_end - pd.Timedelta(days=1))]).sort_index()
    cl = {v: x[~x.index.duplicated(keep="last")] for v, x in cl.items()}
    mins = minute_block(bars, cl).astype(np.float32)
    three = composite({v: cl[v] for v in ("binance", "bybit", "okx")})
    basis3 = (cl["binance"] - three).dropna()
    basis_iq = (cl["binance"] - iq_price(cl, WEIGHTS)).dropna()
    times = pd.date_range(data_start, test_end, freq=f"{GRID_S}s", inclusive="left")
    N = len(times)
    X = np.full((N, len(COLS)), np.nan, np.float32)
    lab = {k: np.full(N, np.nan, np.float32) for k in ("y3", "yiq", "ybn", "yiq20", "yiq30")}
    P = pd.read_parquet(PRED)
    base = {"t": P.index, "y": np.full(len(P), np.nan)}
    months = _months(data_start, test_end - pd.Timedelta(seconds=1))
    pos = {c: i for i, c in enumerate(COLS)}
    prev_tail = None
    for k, ym in enumerate(months):
        cur = sec_month(ym)
        nxt = sec_month(months[k + 1]).iloc[:7200] if k + 1 < len(months) else cur.iloc[:0]
        parts = [x for x in (prev_tail, cur, nxt) if x is not None and len(x)]
        sec = pd.concat(parts).sort_index()
        sec = sec[~sec.index.duplicated(keep="last")]
        prev_tail = cur.iloc[-(HIST_S + 120):]
        m0 = pd.Timestamp(ym + "-01", tz="UTC")
        rows = np.flatnonzero((times >= m0) & (times < m0 + pd.offsets.MonthBegin(1)))
        if not len(rows) or sec.empty:
            log(f"  {ym}: sin datos de 1 s")
            continue
        t = times[rows]
        mb = mins.reindex(t.floor("min"))
        sl = sliding_block(sec, t, mb["vol"].to_numpy(np.float64))
        for c in FEATURES + list(COMP):
            X[rows, pos[c]] = mb[c].to_numpy(np.float32)
        for c in SLIDE:
            X[rows, pos[c]] = sl[c].to_numpy(np.float32)
        si, sc = sec.index, sec["c"].to_numpy(np.float64)
        t_in = (t + pd.Timedelta(seconds=DELAY_S)).to_numpy()
        t_out = (t + pd.Timedelta(seconds=DELAY_S + DUR_S)).to_numpy()
        lab["y3"][rows] = outcome(t_in, t_out, si, sc, basis3)
        lab["ybn"][rows] = outcome(t_in, t_out, si, sc, None)
        if m0 >= test_start:
            lab["yiq"][rows] = outcome(t_in, t_out, si, sc, basis_iq)
            for L in DEMORAS_INFO:
                a = (t + pd.Timedelta(seconds=L)).to_numpy()
                b = (t + pd.Timedelta(seconds=L + DUR_S)).to_numpy()
                lab[f"yiq{L}"][rows] = outcome(a, b, si, sc, basis_iq)
            br = np.flatnonzero((base["t"] >= m0) & (base["t"] < m0 + pd.offsets.MonthBegin(1)))
            if len(br):
                tb_ = base["t"][br]
                base["y"][br] = outcome((tb_ + pd.Timedelta(seconds=60)).to_numpy(),
                                        (tb_ + pd.Timedelta(seconds=60 + DUR_S)).to_numpy(), si, sc, basis_iq)
        log(f"  {ym}: {len(rows):,} decisiones, {np.isfinite(X[rows]).all(axis=1).sum():,} completas")
    return times, X, lab, P.assign(y_iq=base["y"])


def walk_forward(times, X, y, cfg, log=print) -> np.ndarray:
    st, ec = cfg["study"], cfg["execution"]
    ok = np.isfinite(X).all(axis=1)
    valid = ok & np.isfinite(y) & (y != 0)
    label_end = pd.DatetimeIndex(times + pd.Timedelta(minutes=5))
    p = np.full(len(times), np.nan)
    for fold in make_folds(TEST_START, TEST_END, 1, st["train_months"], st["calib_frac"]):
        fit, cal, test = fold.masks(times, label_end)
        fit_rows = np.flatnonzero(fit & valid)
        fit_rows = fit_rows[:: coprime_step(len(fit_rows), st["max_fit_rows"])]
        cal_rows = np.flatnonzero(cal & valid)
        test_rows = np.flatnonzero(test & ok)
        df = lambda r: pd.DataFrame(X[r], columns=COLS)  # noqa: E731
        _, (pc, pt) = fit_predict_proba("gbm", df(fit_rows), (y[fit_rows] == 1).astype(int),
                                        [df(cal_rows), df(test_rows)], seed=ec["seed"],
                                        max_rows=st["max_fit_rows"], features=COLS)
        p[test_rows] = Calibrator().fit(pc, (y[cal_rows] == 1).astype(int)).transform(pt)
        log(f"  {fold.name}: ajuste={len(fit_rows):,} calibración={len(cal_rows):,} prueba={len(test_rows):,}")
    return p


def run(out_dir: Path = Path("results/estudio50"), n_boot: int = 1000, log=print) -> dict:
    cfg = load_config("config/research.toml")  # solo se lee
    log("Variables en la rejilla de 10 s y etiquetas…")
    times, X, lab, base = build(log=log)
    log("Walk-forward mes a mes (etiqueta: compuesto de 3 bolsas)…")
    p = walk_forward(times, X, lab["y3"], cfg, log)
    sel = np.flatnonzero(~np.isnan(p))
    T, p_s = times[sel], p[sel]
    y = {k: v[sel].astype(float) for k, v in lab.items()}
    be = 1 / (1 + PAYOUT)
    bt = pd.DatetimeIndex(base.index)
    bp, bq, by = base["p"].to_numpy(), base["q"].to_numpy(), base["y_iq"].to_numpy()

    def ours(umbral, judge="yiq", cooldown=COOLDOWN_S, mask=None, nb=200, level=0.95):
        yy = y[judge]
        valid = ~np.isnan(yy) & (np.ones(len(yy), bool) if mask is None else mask)
        keep, side = take_signals(T, p_s, valid, umbral, cooldown)
        return summarize(T[keep], side[keep] * yy[keep], n_boot=nb, level=level), keep

    def baseline(umbral, mask=None, nb=200, level=0.95):
        valid = ~np.isnan(by) & (np.ones(len(by), bool) if mask is None else mask)
        keep, side = take_signals(bt, bp, valid, umbral, COOLDOWN_S, q=np.nan_to_num(bq))
        return summarize(bt[keep], side[keep] * by[keep], n_boot=nb, level=level)

    rep = {"estudio": "Estudio 50 — blitz continuo: decisión cada 10 s (pre-registro en docs/01)",
           "git_sha": git_sha(), "periodo_prueba": [TEST_START, TEST_END], "pago": PAYOUT, "equilibrio": be,
           "decisiones_con_prediccion": int(len(sel)), "hipotesis": {}, "informativo": {}}
    user = (T.hour >= 2) & (T.hour < 6)
    buser = (bt.hour >= 2) & (bt.hour < 6)
    for h, (umbral, piso) in HYPS.items():
        x, keep = ours(umbral, nb=n_boot, level=1 - ALPHA)
        ref = baseline(umbral, nb=n_boot, level=1 - ALPHA)
        crit = {"min_300": x["operaciones"] >= 300, "p_bonferroni": x["p"] < ALPHA, "wilson": x["lo95"] > be,
                "ev_ic": (x["ev_ic"][0] or -1) > 0, "meses_60": x["meses_ev_positivo"] >= 0.6,
                "mas_senales": x["por_dia"] >= MIN_RATIO * ref["por_dia"],
                "acierto_minimo": (x["acierto"] or 0) >= piso}
        x.update({"umbral": umbral, "acierto_minimo": piso, "referencia_blitz_actual": ref, "criterios": crit,
                  "pasa": all(crit.values())})
        rep["hipotesis"][h] = x
        sec_of = T[keep].second
        res = np.asarray(lab["yiq"][sel][keep], float) * np.where(p_s[keep] >= 0.5, 1, -1)
        por_seg = {}
        for s_ in range(0, 60, GRID_S):
            r = res[sec_of == s_]
            r = r[~np.isnan(r)]
            nd = int((r != 0).sum())
            por_seg[str(s_)] = {"operaciones": int(len(r)), "acierto": float((r > 0).sum() / nd) if nd else None}
        info = {
            "horario_usuario": ours(umbral, mask=user)[0], "horario_usuario_referencia": baseline(umbral, mask=buser),
            "sin_espera": ours(umbral, cooldown=0)[0],
            "juicio_compuesto_3": ours(umbral, judge="y3")[0], "juicio_binance": ours(umbral, judge="ybn")[0],
            **{f"demora_{L}s": ours(umbral, judge=f"yiq{L}")[0] for L in DEMORAS_INFO},
            "por_segundo_del_minuto": por_seg,
        }
        for d in info.values():
            if isinstance(d, dict):
                d.pop("mensual", None)
        info["horario_usuario"]["por_noche"] = info["horario_usuario"]["por_dia"]
        info["horario_usuario_referencia"]["por_noche"] = info["horario_usuario_referencia"]["por_dia"]
        rep["informativo"][h] = info
        fmt = lambda v, f: "—" if v is None else format(v, f)  # noqa: E731 (sin operaciones: None)
        log(f"{h} (p ≥ {umbral}): pasa={x['pasa']} | {x['operaciones']} ops ({x['por_dia']:.1f}/día), acierto "
            f"{fmt(x['acierto'], '.4f')} [{fmt(x['lo95'], '.4f')}] EV {fmt(x['ev'], '+.4f')} | referencia "
            f"{ref['operaciones']} ops ({ref['por_dia']:.1f}/día) acierto {fmt(ref['acierto'], '.4f')} | {crit}")
    rep["informativo"]["umbrales"] = {
        str(u): {"nuevo": {k: v for k, v in ours(u)[0].items() if k != "mensual"},
                 "referencia": {k: v for k, v in baseline(u).items() if k != "mensual"}} for u in UMBRALES_INFO}
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"p": p_s.astype(np.float32), **{k: v.astype(np.float32) for k, v in y.items()}},
                 index=T).to_parquet(out_dir / "predicciones.parquet")
    (out_dir / "resultado.json").write_text(json.dumps(jsonable(rep), indent=2, ensure_ascii=False), encoding="utf-8")
    return rep
