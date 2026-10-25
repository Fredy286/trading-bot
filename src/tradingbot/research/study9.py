"""Estudio 9 (pre-registro en docs/01, commit 1548ecb): la regla de redes «RSI diario y semanal en sobrecompra →
solo ventas (y al revés), confirmar la estructura de 4H y operar en 15M», probada tal cual.

Binaria a 15 min con entrada 1 min después (manual), sin solapamiento, 2022-01 → 2025-08, en BTC, ETH, oro y
EUR/USD. La regla no se entrena: es una prueba directa.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from ..data import store
from ..data.clean import to_canonical
from ..instruments import get_instrument
from .experiment import git_sha, jsonable
from .features import _rsi
from .labels import decision_mask, make_labels
from .metrics import binom_pvalue_greater, block_bootstrap_mean, wilson
from .study3 import load, spot_bars

START, END = "2022-01-01", "2025-09-01"
HORIZON, ENTRY_DELAY = 15, 2
ALPHA = 0.0125  # Bonferroni, 4 instrumentos
SYMBOLS = {"H9-BTC": "BTCUSDT", "H9-ETH": "ETHUSDT", "H9-XAU": "XAUUSD", "H9-EUR": "EURUSD"}
FREQ = {"D": ("1D", pd.Timedelta(days=1)), "W": ("W-MON", pd.Timedelta(days=7)), "4H": ("4h", pd.Timedelta(hours=4))}


def closed_candles(bars: pd.DataFrame, key: str) -> pd.DataFrame:
    """Velas de marco superior (cortes en UTC; semanas de lunes a domingo) con la hora en que quedan cerradas."""
    rule, length = FREQ[key]
    g = bars[["o", "h", "l", "c"]].resample(rule, label="left", closed="left")
    tf = pd.DataFrame({"o": g["o"].first(), "h": g["h"].max(), "l": g["l"].min(), "c": g["c"].last()}).dropna()
    tf["cerrada"] = tf.index + length
    return tf


def last_closed(bars: pd.DataFrame, tf: pd.DataFrame, values: pd.DataFrame) -> pd.DataFrame:
    """Para cada minuto t, `values` de la última vela de marco superior cerrada al cierre de t (apertura + 1 min)."""
    close_t = (bars.index + pd.Timedelta(minutes=1)).asi8
    pos = np.searchsorted(pd.DatetimeIndex(tf["cerrada"]).asi8, close_t, side="right") - 1
    out = values.to_numpy(float)[np.clip(pos, 0, None)]
    out[pos < 0] = np.nan
    return pd.DataFrame(out, index=bars.index, columns=values.columns)


def rule_sides(bars: pd.DataFrame) -> dict[str, np.ndarray]:
    """Lado por minuto (+1 compra, −1 venta, 0 nada) de la regla y de sus variantes informativas."""
    d, w, h4 = (closed_candles(bars, k) for k in ("D", "W", "4H"))
    rsi = pd.concat([last_closed(bars, d, pd.DataFrame({"rsi_d": _rsi(d["c"])})),
                     last_closed(bars, w, pd.DataFrame({"rsi_w": _rsi(w["c"])}))], axis=1)
    st = pd.DataFrame({"lower": (h4["h"] < h4["h"].shift(1)) & (h4["c"] < h4["c"].shift(1)),
                       "higher": (h4["l"] > h4["l"].shift(1)) & (h4["c"] > h4["c"].shift(1))}).astype(float)
    st = last_closed(bars, h4, st)
    ob = ((rsi["rsi_d"] >= 70) & (rsi["rsi_w"] >= 70)).to_numpy()
    os_ = ((rsi["rsi_d"] <= 30) & (rsi["rsi_w"] <= 30)).to_numpy()
    dm = decision_mask(bars.index, HORIZON)
    no_4h = np.where(ob, -1, np.where(os_, 1, 0)) * dm
    rule = np.where(ob & (st["lower"].to_numpy() == 1), -1, np.where(os_ & (st["higher"].to_numpy() == 1), 1, 0)) * dm
    return {"regla": rule, "sin_4h": no_4h, "al_reves": -rule}


def simulate(bars: pd.DataFrame, side: np.ndarray, point: float) -> pd.DataFrame:
    lab = make_labels(bars, HORIZON, ENTRY_DELAY, point)
    dirs = lab["dir"].to_numpy()
    rows, busy = [], -1
    for t in np.flatnonzero(side != 0):
        if t <= busy or np.isnan(dirs[t]):
            continue
        busy = t + ENTRY_DELAY + HORIZON - 1  # vence al cierre de t+16
        res = int(dirs[t] * side[t])
        rows.append({"time": bars.index[t], "lado": int(side[t]), "resultado": res,
                     "pnl": 0.0 if res == 0 else (0.85 if res > 0 else -1.0)})
    return pd.DataFrame(rows, columns=["time", "lado", "resultado", "pnl"])


def evaluate(tr: pd.DataFrame, n_boot: int = 2000) -> dict:
    n_all = len(tr)
    if not n_all:
        return {"operaciones": 0, "pasa": False}
    nt = tr[tr["resultado"] != 0]
    n, wins = len(nt), int((nt["resultado"] > 0).sum())
    lo, hi = wilson(wins, n) if n else (float("nan"), float("nan"))
    be = 1 / 1.85
    p = binom_pvalue_greater(wins, n, be) if n else 1.0
    t = pd.DatetimeIndex(tr["time"])
    week = t.strftime("%G-%V")
    b = block_bootstrap_mean(tr["pnl"].to_numpy(), week, n_boot=n_boot, level=1 - ALPHA)
    crit = {"min_300": n_all >= 300, "p_bonferroni": p < ALPHA, "wilson": lo > be, "ev_ic_semanal": b["lo"] > 0}
    return {"operaciones": n_all, "sin_empate": n, "aciertos": wins, "acierto": wins / n if n else None,
            "lo95": float(lo), "hi95": float(hi), "p": p, "ev": b["mean"], "ev_ic98_75": [b["lo"], b["hi"]],
            "semanas_con_operaciones": int(len(set(week))), "ventas": int((tr["lado"] < 0).sum()),
            "compras": int((tr["lado"] > 0).sum()), "criterios": crit, "pasa": all(crit.values())}


def load_bars(symbol: str, root3: Path, root: Path) -> pd.DataFrame:
    if symbol in ("BTCUSDT", "ETHUSDT"):
        bars = spot_bars(load(root3, symbol, "spot"))
    else:
        bars, _ = to_canonical(store.load(root, get_instrument(symbol), source="histdata"), fill_gaps=True)
    return bars[(bars.index >= pd.Timestamp("2021-01-01", tz="UTC")) & (bars.index < pd.Timestamp(END, tz="UTC"))]


def run(root3: Path = Path("data/raw/estudio3"), root: Path = Path("data/raw"),
        out_dir: Path = Path("results/estudio9"), n_boot: int = 2000) -> dict:
    res = {}
    for h, sym in SYMBOLS.items():
        bars = load_bars(sym, root3, root)
        sides = rule_sides(bars)
        test = (bars.index >= pd.Timestamp(START, tz="UTC")).astype(int)
        point = get_instrument(sym).point
        out = {k: evaluate(simulate(bars, s * test, point), n_boot) for k, s in sides.items()}
        res[h] = {"simbolo": sym, "regla": out["regla"],
                  "informativo": {"sin_confirmacion_4h": out["sin_4h"], "al_reves_seguir_tendencia": out["al_reves"]}}
    report = {"estudio": "Estudio 9 — RSI diario/semanal + 4H + 15M (pre-registro 1548ecb)", "git_sha": git_sha(),
              "periodo": [START, END], "resultados": res, "pasa_alguna": any(r["regla"]["pasa"] for r in res.values())}
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "resultado.json").write_text(json.dumps(jsonable(report), indent=2, ensure_ascii=False),
                                            encoding="utf-8")
    return report
