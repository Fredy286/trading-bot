"""Estudio 45 (pre-registro en docs/01, commit 74e4ec1): las cinco estrategias típicas de ChatGPT para BTC (EMA 9/21,
RSI 30/70, MACD, Bollinger, Supertrend), en largo y sin apalancamiento sobre velas de 4 h de Binance. En cada
semestre se eligen las 2 mejores y se miden en el semestre siguiente. Además: apalancamiento que haría falta para las
cifras del video (+927 % y +1 588 % en 6 meses).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from .experiment import git_sha, jsonable
from .metrics import binom_pvalue_greater
from .study3 import load
from .study20 import _read_days

COST = 0.001  # 0,1 % por lado (contado de Binance)
END = pd.Timestamp("2026-10-26", tz="UTC")  # excluido: nada posterior al 2026-10-25
FIRST = pd.Timestamp("2021-01-01", tz="UTC")
VIDEO = {"+927 %": 10.27, "+1 588 %": 16.88}  # capital final / inicial


def bars(rule: str, root3: Path = Path("data/raw/estudio3"),
         daily: Path = Path("data/processed/senal/diario")) -> pd.DataFrame:
    m = pd.concat([load(root3, "BTCUSDT", "spot"), _read_days(Path(daily) / "1m", "2026-10-01", "2026-10-26")])
    m = m[~m.index.duplicated(keep="last")].sort_index()
    m = m[m.index < END]
    g = m.resample(rule, label="left", closed="left")
    return pd.DataFrame({"o": g["o"].first(), "h": g["h"].max(), "l": g["l"].min(), "c": g["c"].last()}).dropna()


def _ema(x: pd.Series, n: int) -> pd.Series:
    return x.ewm(span=n, adjust=False).mean()


def _rma(x: pd.Series, n: int) -> pd.Series:
    return x.ewm(alpha=1 / n, adjust=False).mean()


def rsi(c: pd.Series, n: int = 14) -> pd.Series:
    d = c.diff()
    up, dn = _rma(d.clip(lower=0), n), _rma(-d.clip(upper=0), n)
    return 100 - 100 / (1 + up / dn)


def _state(enter: np.ndarray, leave: np.ndarray) -> np.ndarray:
    """Posición 0/1 con eventos de entrada y salida; la salida solo cuenta estando dentro."""
    pos, inside = np.zeros(len(enter)), 0
    for i in range(len(enter)):
        if inside and leave[i]:
            inside = 0
        elif not inside and enter[i]:
            inside = 1
        pos[i] = inside
    return pos


def supertrend_up(b: pd.DataFrame, n: int = 10, mult: float = 3.0) -> np.ndarray:
    h, l, c = b["h"].to_numpy(), b["l"].to_numpy(), b["c"].to_numpy()
    tr = np.maximum(h - l, np.maximum(np.abs(h - np.r_[c[0], c[:-1]]), np.abs(l - np.r_[c[0], c[:-1]])))
    atr = _rma(pd.Series(tr), n).to_numpy()
    mid = (h + l) / 2
    up_b, dn_b = mid - mult * atr, mid + mult * atr
    trend = np.ones(len(c))
    fu, fd = up_b.copy(), dn_b.copy()
    for i in range(1, len(c)):
        fu[i] = max(up_b[i], fu[i - 1]) if c[i - 1] > fu[i - 1] else up_b[i]
        fd[i] = min(dn_b[i], fd[i - 1]) if c[i - 1] < fd[i - 1] else dn_b[i]
        trend[i] = 1 if c[i] > fd[i - 1] else (-1 if c[i] < fu[i - 1] else trend[i - 1])
    return (trend > 0).astype(float)


def positions(b: pd.DataFrame) -> pd.DataFrame:
    """Posición decidida al cierre de cada vela (1 = comprado)."""
    c = b["c"]
    r = rsi(c)
    macd = _ema(c, 12) - _ema(c, 26)
    sma, sd = c.rolling(20).mean(), c.rolling(20).std(ddof=0)
    out = pd.DataFrame(index=b.index)
    out["EMA 9/21"] = (_ema(c, 9) > _ema(c, 21)).astype(float)
    out["RSI 30/70"] = _state(((r > 30) & (r.shift(1) <= 30)).to_numpy(), ((r < 70) & (r.shift(1) >= 70)).to_numpy())
    out["MACD"] = (macd > _ema(macd, 9)).astype(float)
    out["Bollinger"] = _state((c < sma - 2 * sd).to_numpy(), (c > sma).to_numpy())
    out["Supertrend"] = supertrend_up(b)
    return out


def net_returns(b: pd.DataFrame, pos: pd.DataFrame, cost: float = COST, lev: float = 1.0) -> pd.DataFrame:
    """Rendimiento de cada vela t (del cierre de t − 1 al de t) con la posición decidida en t − 1; el costo se paga
    al cambiar de posición, sobre el nocional (apalancamiento incluido)."""
    r = b["c"].pct_change()
    held = pos.shift(1).fillna(0.0)
    turn = pos.diff().abs().fillna(pos.iloc[0]).shift(1).fillna(0.0)
    return lev * held.mul(r, axis=0) - lev * cost * turn


def windows(end: pd.Timestamp = END, first: pd.Timestamp = FIRST) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    """Semestres contiguos anclados al final (el último termina el 2026-10-25), sin empezar antes de `first`."""
    out, b = [], end
    while b - pd.DateOffset(months=6) >= first:
        a = b - pd.DateOffset(months=6)
        out.append((a, b))
        b = a
    return out[::-1]


def window_returns(net: pd.DataFrame, wins) -> pd.DataFrame:
    rows = {}
    for a, b in wins:
        x = net[(net.index >= a) & (net.index < b)]  # la vela t (abre en t) va del cierre anterior (en t) a t + 4 h
        rows[f"{a:%Y-%m-%d}→{b:%Y-%m-%d}"] = (1 + x).prod() - 1
    return pd.DataFrame(rows).T


def leverage_for(net1: pd.Series, target: float) -> dict:
    """Apalancamiento constante (de 1 a 50) para que el capital final llegue a `target` veces el inicial; con su
    mayor caída. Si el capital toca 0, queda liquidado (sin contar los movimientos dentro de cada vela)."""
    best = None
    for lev in np.arange(1.0, 50.01, 0.25):
        eq = np.cumprod(np.maximum(1 + lev * net1.to_numpy(), 0.0))
        if eq[-1] >= target:
            peak = np.maximum.accumulate(eq)
            best = {"apalancamiento": float(lev), "capital_final": float(eq[-1]),
                    "mayor_caida": float(1 - (eq / peak).min()), "liquidado": bool((eq <= 0).any())}
            break
    return best or {"apalancamiento": None, "nota": "no se alcanza con 50x"}


def run(out_dir: Path = Path("results/estudio45"), log=print) -> dict:
    rep = {"estudio": "Estudio 45 — las 5 estrategias típicas de ChatGPT para BTC (pre-registro 74e4ec1)",
           "git_sha": git_sha(), "costo_por_lado": COST, "temporalidades": {}}
    wins = windows()
    for rule in ("4h", "1h"):
        b = bars(rule)
        pos = positions(b)
        net = net_returns(b, pos)
        wr = window_returns(net, wins)
        bh = pd.Series({f"{a:%Y-%m-%d}→{e:%Y-%m-%d}": b["c"][b.index < e].iloc[-1] / b["c"][b.index < a].iloc[-1] - 1
                        for a, e in wins})
        pares = []
        for k in range(len(wr) - 1):
            top2 = list(wr.iloc[k].sort_values(ascending=False).index[:2])
            nxt = wr.iloc[k + 1]
            pares.append({"elige_en": wr.index[k], "elegidas": top2,
                          "rend_elegidas_al_elegir": float(wr.iloc[k][top2].mean()),
                          "mide_en": wr.index[k + 1], "rend_elegidas_despues": float(nxt[top2].mean()),
                          "promedio_5_despues": float(nxt.mean()), "comprar_y_mantener_despues": float(bh.iloc[k + 1])})
        d = np.array([p["rend_elegidas_despues"] - p["promedio_5_despues"] for p in pares])
        w, n = int((d > 0).sum()), int((d != 0).sum())
        last = wr.iloc[-1].sort_values(ascending=False)
        net_last = net[(net.index >= wins[-1][0]) & (net.index < wins[-1][1])]
        sin_costo = window_returns(net_returns(b, pos, cost=0.0), wins[-1:]).iloc[0]
        apal = {}
        for name in last.index[:2]:
            unit = net_returns(b, pos[[name]], lev=1.0)[name]
            unit = unit[(unit.index >= wins[-1][0]) & (unit.index < wins[-1][1])]
            apal[name] = {k: leverage_for(unit, v) for k, v in VIDEO.items()}
        res = {"semestres": {k: {s: float(v) for s, v in row.items()} for k, row in wr.iterrows()},
               "comprar_y_mantener": {k: float(v) for k, v in bh.items()}, "pares": pares,
               "H45": {"ganan_al_promedio": w, "pares": n, "p": binom_pvalue_greater(w, n, 0.5) if n else 1.0,
                       "pasa": bool(n and binom_pvalue_greater(w, n, 0.5) < 0.05)},
               "ultimo_semestre": {"rango": wr.index[-1], "con_costos": {s: float(v) for s, v in last.items()},
                                   "sin_costos": {s: float(v) for s, v in sin_costo.items()},
                                   "comprar_y_mantener": float(bh.iloc[-1]),
                                   "operaciones": {s: int(pos[s][(pos.index >= wins[-1][0]) & (pos.index < wins[-1][1])]
                                                          .diff().abs().sum() / 2) for s in pos.columns},
                                   "apalancamiento_para_el_video": apal},
               "velas": int(len(net_last))}
        rep["temporalidades"][rule] = res
        log(f"{rule}: H45 {w}/{n} pares (p = {res['H45']['p']:.3f}) | último semestre: "
            + ", ".join(f"{s} {v:+.1%}" for s, v in last.items()) + f" | comprar y mantener {bh.iloc[-1]:+.1%}")
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "resultado.json").write_text(json.dumps(jsonable(rep), indent=2, ensure_ascii=False), encoding="utf-8")
    return rep
