"""Estudio 22 (pre-registro en docs/01, commit f020d9b): reglas de comunidades de binarias, desarmadas y probadas.

Cuadrantes brasileños (MHI, Milhão, Torres Gêmeas, …), indicadores de bots de GitHub, Bollinger de smart-lab,
catalogación por horario y Turn Over, en BTC/USDT, EUR/USD, GBP/USD, USD/JPY y XAU/USD. Se mide la primera entrada
(G0) con entrada en la apertura de la vela objetivo y salida en su cierre; el gale solo se informa.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from .experiment import git_sha, jsonable
from .metrics import binom_pvalue_greater, wilson
from .study3 import load

PAYOUT, BE = 0.85, 1 / 1.85
MAIN = ("2025-09-01", "2026-10-26")
INFO = ("2021-01-01", "2025-09-01")
GALE = (1.0, 2.18, 4.74)
SYMBOLS = ("BTCUSDT", "EURUSD", "GBPUSD", "USDJPY", "XAUUSD")

# Cuadrantes: (posición de entrada 0–4, desplazamientos de las velas miradas, tipo)
QUAD = {
    "MHI1_minoria": (0, (3, 2, 1), "min"), "MHI2_minoria": (1, (4, 3, 2), "min"), "MHI3_minoria": (2, (5, 4, 3), "min"),
    "MHI1_mayoria": (0, (3, 2, 1), "may"), "MHI2_mayoria": (1, (4, 3, 2), "may"), "MHI3_mayoria": (2, (5, 4, 3), "may"),
    "Milhao_mayoria": (0, (5, 4, 3, 2, 1), "may"), "Milhao_minoria": (0, (5, 4, 3, 2, 1), "min"),
    "Vituxo_mayoria": (2, (7, 6, 5), "may"), "Torres_Gemeas": (4, (4,), "may"), "Tres_Vizinhos": (3, (1,), "may"),
    "Padrao_23": (1, (1,), "may"), "Melhor_de_3": (2, (6, 5, 4), "may"), "Padrao_3x1": (4, (4, 3, 2), "min"),
    "C3": (0, (5,), "may"), "Moonwalker": (0, (3,), "min"), "Bullex_3_velas": (0, (3, 2, 1), "rev3"),
}


def load_bars(symbol: str, root3: Path = Path("data/raw/estudio3"), daily: Path = Path("data/processed/senal/diario"),
              hd_old: Path = Path("data/raw/histdata"), hd_new: Path = Path("data/raw/histdata_2026/histdata")):
    """Velas de 1 min (o, h, l, c) en una rejilla completa de minutos (NaN donde no hay vela)."""
    if symbol == "BTCUSDT":
        days = pd.date_range("2026-10-01", "2026-10-26", freq="D", inclusive="left")
        oct_ = [pd.read_parquet(Path(daily) / "1m" / f"{d:%Y-%m-%d}.parquet") for d in days]
        df = pd.concat([load(root3, "BTCUSDT", "spot"), *oct_])[["o", "h", "l", "c"]]
    else:
        old = [pd.read_parquet(f) for f in sorted((Path(hd_old) / symbol).glob("20*.parquet")) if f.stem < "2025"]
        new = [pd.read_parquet(f) for f in sorted((Path(hd_new) / symbol).glob("20*.parquet"))]
        df = pd.concat(old + new)[["bid_o", "bid_h", "bid_l", "bid_c"]]
        df.columns = ["o", "h", "l", "c"]
    df = df[~df.index.duplicated(keep="last")].sort_index()
    df = df[(df.index >= pd.Timestamp(INFO[0], tz="UTC")) & (df.index < pd.Timestamp(MAIN[1], tz="UTC"))]
    grid = pd.date_range(df.index[0], df.index[-1], freq="min", tz="UTC")
    return df.reindex(grid)


def color(o: np.ndarray, c: np.ndarray) -> np.ndarray:
    d = c - o
    return np.where(np.isnan(d), np.nan, np.sign(np.where(np.abs(d) < 1e-9, 0.0, d)))


def lag(a: np.ndarray, k: int) -> np.ndarray:
    out = np.full_like(a, np.nan)
    if k > 0:
        out[k:] = a[:-k]
    elif k < 0:
        out[:k] = a[-k:]
    else:
        out[:] = a
    return out


def quad_rule(col: np.ndarray, minute: np.ndarray, entry: int, offs: tuple, kind: str, shift: int = 0) -> np.ndarray:
    """Dirección (±1, NaN = no operar) en cada vela objetivo t. `shift` ≠ 0 = placebo sin alineación al reloj."""
    looked = np.vstack([lag(col, k) for k in offs])
    bad = np.isnan(looked).any(0) | (looked == 0).any(0)
    s = looked.sum(0)
    if kind == "may":
        d = np.sign(s)
    elif kind == "min":
        d = -np.sign(s)
    else:  # rev3: las tres iguales → contra
        d = np.where(np.abs(s) == len(offs), -np.sign(s), np.nan)
    on = ((minute - shift) % 5) == entry
    return np.where(on & ~bad, d, np.nan)


def _sma(x, n):
    return pd.Series(x).rolling(n).mean().to_numpy()


def _ema(x, n):
    return pd.Series(x).ewm(span=n, adjust=False).mean().to_numpy()


def _rsi(x, n=14):
    d = pd.Series(x).diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return (100 - 100 / (1 + up / dn)).to_numpy()


def indicator_rules(bars: pd.DataFrame) -> dict[str, np.ndarray]:
    """Reglas de indicadores: la señal sale al cierre de la vela s y se opera la vela s + 1 (si existe)."""
    real = bars.dropna()
    c, h, l = real["c"].to_numpy(), real["h"].to_numpy(), real["l"].to_numpy()
    out = {}
    s3, s8 = _sma(c, 3), _sma(c, 8)
    down = (s3 < s8) & (lag(s3, 1) >= lag(s8, 1)) & (c < lag(c, 1)) & (lag(c, 1) < lag(c, 2))
    up = (s3 > s8) & (lag(s3, 1) <= lag(s8, 1)) & (c > lag(c, 1)) & (lag(c, 1) > lag(c, 2))
    out["SMA3_SMA8_3cierres"] = np.where(up, 1.0, np.where(down, -1.0, np.nan))
    e20, e50, rsi = _ema(c, 20), _ema(c, 50), _rsi(c)
    rng = (pd.Series(h).rolling(20).max() - pd.Series(l).rolling(20).min()).to_numpy() / c
    trend_up = (e20 > e50) & (lag(e20, 1) > lag(e50, 1))
    trend_dn = (e20 < e50) & (lag(e20, 1) < lag(e50, 1))
    mom = c - lag(c, 2)
    ok = rng >= 0.0005
    out["EMA20_50_RSI14"] = np.where(ok & trend_up & (rsi >= 52) & (mom > 0), 1.0,
                                     np.where(ok & trend_dn & (rsi <= 48) & (mom < 0), -1.0, np.nan))
    e5 = _ema(c, 5)
    cu = (e5 > e20) & (lag(e5, 1) <= lag(e20, 1)) & (rsi > 50)
    cd = (e5 < e20) & (lag(e5, 1) >= lag(e20, 1)) & (rsi < 50)
    out["EMA5_20_RSI50"] = np.where(cu, 1.0, np.where(cd, -1.0, np.nan))
    sig = {}
    nxt = real.index + pd.Timedelta(minutes=1)
    for k, d in out.items():
        sig[k] = pd.Series(d, index=nxt).reindex(bars.index).to_numpy()  # dirección en la vela objetivo
    # Bollinger (20, 2) con reversión, 21–24 UTC; resultado a 3 min (apertura s+1 → cierre s+3)
    mid, sd = _sma(c, 20), pd.Series(c).rolling(20).std(ddof=0).to_numpy()
    hour = real.index.hour.to_numpy()
    bb = np.where(c > mid + 2 * sd, -1.0, np.where(c < mid - 2 * sd, 1.0, np.nan))
    sig["Bollinger_rev_3min_21a24UTC"] = pd.Series(np.where(hour >= 21, bb, np.nan), index=nxt).reindex(bars.index).to_numpy()
    return sig


def catalog_rule(col: np.ndarray, idx: pd.DatetimeIndex, days: int = 10, thr: float = 0.8) -> np.ndarray:
    """«Lista de señales»: color dominante de cada HH:MM en los últimos `days` días con vela → al día siguiente."""
    s = pd.Series(col, index=idx).dropna()
    tab = pd.DataFrame({"d": s.index.floor("D"), "m": s.index.hour * 60 + s.index.minute, "c": s.to_numpy()})
    piv = tab.pivot_table(index="d", columns="m", values="c", aggfunc="first")
    green = (piv == 1).astype(float).where(piv.notna())
    red = (piv == -1).astype(float).where(piv.notna())
    cnt = piv.notna().astype(float)
    # Últimos `days` días de cada columna con vela, excluyendo el día actual
    g = green.shift(1).rolling(days, min_periods=1).sum()
    r = red.shift(1).rolling(days, min_periods=1).sum()
    n = cnt.shift(1).rolling(days, min_periods=1).sum()
    full = n == days
    d = np.where(full & (g / n >= thr), 1.0, np.where(full & (r / n >= thr), -1.0, np.nan))
    out = pd.DataFrame(d, index=piv.index, columns=piv.columns).stack()
    t = pd.DatetimeIndex([dd + pd.Timedelta(minutes=int(m)) for dd, m in out.index])
    return pd.Series(out.to_numpy(), index=t).reindex(idx).to_numpy()


def turn_over(bars: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """Vela de 15 min de :45 → contra en la de :00; devuelve (dirección, resultado) en la rejilla de 15 min."""
    o = bars["o"].resample("15min").first()
    c = bars["c"].resample("15min").last()
    first_ok = bars["o"].resample("15min").apply(lambda x: not np.isnan(x.iloc[0]) if len(x) else False)
    last_ok = bars["c"].resample("15min").apply(lambda x: not np.isnan(x.iloc[-1]) if len(x) else False)
    good = first_ok.astype(bool) & last_ok.astype(bool)
    col15 = np.where(good, color(o.to_numpy(), c.to_numpy()), np.nan)
    prev = lag(col15, 1)
    d = np.where((o.index.minute == 0) & (prev != 0), -prev, np.nan)
    return pd.Series(d, index=o.index), pd.Series(col15, index=o.index)


def score(d: np.ndarray, res: np.ndarray, times: pd.DatetimeIndex) -> dict:
    take = ~np.isnan(d) & ~np.isnan(res) & (d != 0)
    r = d[take] * res[take]
    n, w, ties = int((r != 0).sum()), int((r > 0).sum()), int((r == 0).sum())
    pnl = np.where(r == 0, 0.0, np.where(r > 0, PAYOUT, -1.0))
    month = pd.PeriodIndex(times[take].tz_convert(None), freq="M").astype(str)
    mens = pd.Series(pnl).groupby(np.asarray(month)).mean() if n else pd.Series(dtype=float)
    lo, _ = wilson(w, n) if n else (float("nan"), 0)
    return {"operaciones": int(take.sum()), "sin_doji": n, "aciertos": w, "dojis": ties,
            "acierto": w / n if n else None, "lo95": float(lo),
            "acierto_doji_pierde": w / (n + ties) if n + ties else None,
            "p": binom_pvalue_greater(w, n, BE) if n else 1.0, "ev": float(pnl.mean()) if len(pnl) else None,
            "meses_ev_positivo": float((mens > 0).mean()) if len(mens) else 0.0,
            "mensual": {k: round(float(v), 4) for k, v in mens.items()}}


def gale_cycle(d: np.ndarray, col: np.ndarray, take_mask: np.ndarray) -> dict:
    """Ciclo con hasta 2 gales en las velas siguientes, misma dirección (doji = pierde, como en IQ Option)."""
    r0, r1, r2 = d * col, d * lag(col, -1), d * lag(col, -2)
    m = take_mask & ~np.isnan(r0) & ~np.isnan(r1) & ~np.isnan(r2) & ~np.isnan(d)
    w0, w1, w2 = r0[m] > 0, r1[m] > 0, r2[m] > 0
    s0, s1, s2 = GALE
    pnl = np.where(w0, s0 * PAYOUT, np.where(w1, -s0 + s1 * PAYOUT, np.where(w2, -s0 - s1 + s2 * PAYOUT, -s0 - s1 - s2)))
    return {"ciclos": int(m.sum()), "acierto_ciclo": float((w0 | w1 | w2).mean()) if m.any() else None,
            "ev_ciclo": float(pnl.mean()) if m.any() else None}


def holm(ps: list[float]) -> list[float]:
    order = np.argsort(ps)
    adj, run = np.empty(len(ps)), 0.0
    for rank, i in enumerate(order):
        run = max(run, min(1.0, (len(ps) - rank) * ps[i]))
        adj[i] = run
    return adj.tolist()


def run_symbol(symbol: str, log=print) -> dict:
    bars = load_bars(symbol)
    idx = bars.index
    col = color(bars["o"].to_numpy(), bars["c"].to_numpy())
    minute = idx.minute.to_numpy()
    main = (idx >= pd.Timestamp(MAIN[0], tz="UTC")) & (idx < pd.Timestamp(MAIN[1], tz="UTC"))
    info = idx < pd.Timestamp(INFO[1], tz="UTC")
    out = {}

    def add(name, d, res, times, m_main, m_info, gale=None, placebo=None):
        dm = np.where(m_main, d, np.nan)
        out[name] = {**score(dm, res, times), "informativo_2021_2025": {
            k: v for k, v in score(np.where(m_info, d, np.nan), res, times).items() if k != "mensual"}}
        if gale is not None:
            out[name]["gale2_principal"] = gale_cycle(d, col, m_main)
        if placebo is not None:
            out[name]["placebo_desplazado"] = placebo
        log(f"  {symbol} {name}: {out[name]['operaciones']} ops, acierto {out[name]['acierto']}")

    for name, (entry, offs, kind) in QUAD.items():
        d = quad_rule(col, minute, entry, offs, kind)
        pl = [quad_rule(col, minute, entry, offs, kind, shift=s) for s in (1, 2, 3, 4)]
        pls = [score(np.where(main, p, np.nan), col, idx) for p in pl]
        n_pl = sum(p["sin_doji"] for p in pls)
        plac = {"acierto": sum(p["aciertos"] for p in pls) / n_pl if n_pl else None, "sin_doji": n_pl}
        add(name, d, col, idx, main, info, gale=True, placebo=plac)
    for name, d in indicator_rules(bars).items():
        if name.startswith("Bollinger"):
            # resultado a 3 min (apertura de t → cierre de t + 2), una operación a la vez
            res = color(bars["o"].to_numpy(), lag(bars["c"].to_numpy(), -2))
            res = np.where(np.isnan(lag(col, -1)) | np.isnan(lag(col, -2)), np.nan, res)
            keep, busy = np.full(len(d), np.nan), -1
            for i in np.flatnonzero(~np.isnan(d) & ~np.isnan(res)):
                if i > busy:
                    keep[i], busy = d[i], i + 2
            add(name, keep, res, idx, main, info)
        else:
            add(name, d, col, idx, main, info, gale=True)
    add("Catalogacion_D10_80", catalog_rule(col, idx), col, idx, main, info, gale=True)
    d15, c15 = turn_over(bars)
    t15 = d15.index
    add("Turn_Over_M15", d15.to_numpy(), c15.to_numpy(), t15,
        (t15 >= pd.Timestamp(MAIN[0], tz="UTC")) & (t15 < pd.Timestamp(MAIN[1], tz="UTC")),
        t15 < pd.Timestamp(INFO[1], tz="UTC"))
    return out


def run(out_dir: Path = Path("results/estudio22"), symbols=SYMBOLS, log=print) -> dict:
    rep = {"estudio": "Estudio 22 — estrategias de comunidades de binarias (pre-registro f020d9b)",
           "git_sha": git_sha(), "periodo_principal": MAIN, "pago": PAYOUT, "equilibrio": BE, "reglas": {}}
    for s in symbols:
        rep["reglas"][s] = run_symbol(s, log)
    keys = [(s, r) for s in rep["reglas"] for r in rep["reglas"][s]]
    adj = holm([rep["reglas"][s][r]["p"] for s, r in keys])
    passed = []
    for (s, r), pa in zip(keys, adj):
        x = rep["reglas"][s][r]
        crit = {"min_300": x["operaciones"] >= 300, "holm": pa < 0.05, "wilson": x["lo95"] > BE,
                "meses_60": x["meses_ev_positivo"] >= 0.6}
        x.update({"p_holm": pa, "criterios": crit, "pasa": all(crit.values())})
        if x["pasa"]:
            passed.append(f"{s}:{r}")
    rep["n_hipotesis"], rep["pasan"] = len(keys), passed
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "resultado.json").write_text(json.dumps(jsonable(rep), indent=2, ensure_ascii=False), encoding="utf-8")
    return rep
