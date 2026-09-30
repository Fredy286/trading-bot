"""Variables CAUSALES: el valor en la fila t solo usa velas con marca ≤ t.

La prueba `tests/test_no_lookahead.py` altera las velas posteriores a un instante y verifica que
ninguna variable anterior cambie.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .news import in_release_window

FEATURES: list[str] = [
    "r0", "r1", "r2", "r3", "r4",
    "cum5", "cum15", "cum60", "cum240",
    "lvol15", "lvol60", "lvol240", "vol_ratio",
    "range", "clpos",
    "d_sma20", "d_sma60", "rsi14", "boll_z",
    "spread_vol", "spread_rel", "vol_rel", "notick60",
    "tod_sin", "tod_cos", "dow",
    "sched_next",
]


def _rsi(close: pd.Series, n: int = 14) -> pd.Series:
    diff = close.diff()
    up = diff.clip(lower=0)
    down = (-diff).clip(lower=0)
    au = up.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    ad = down.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    rs = au / ad.replace(0, np.nan)
    rsi = 100 - 100 / (1 + rs)
    return rsi.where(ad > 0, 100.0).where(au.notna())


def compute_features(bars: pd.DataFrame) -> pd.DataFrame:
    c, h, l = bars["c"], bars["h"], bars["l"]
    logc = np.log(c)
    lr = logc.diff()
    vol60 = lr.rolling(60, min_periods=50).std()
    volf = vol60.where(vol60 > 0)

    f = pd.DataFrame(index=bars.index)
    for k in range(5):
        f[f"r{k}"] = lr.shift(k) / volf
    for n in (5, 15, 60, 240):
        f[f"cum{n}"] = (logc - logc.shift(n)) / (volf * np.sqrt(n))
    vol15 = lr.rolling(15, min_periods=12).std()
    vol240 = lr.rolling(240, min_periods=200).std()
    f["lvol15"] = np.log(vol15.where(vol15 > 0))
    f["lvol60"] = np.log(volf)
    f["lvol240"] = np.log(vol240.where(vol240 > 0))
    f["vol_ratio"] = vol15 / vol240.where(vol240 > 0)
    f["range"] = (np.log(h) - np.log(l)) / volf
    rng = (h - l)
    f["clpos"] = ((c - l) / rng.where(rng > 0)).fillna(0.5).where(c.notna())
    sma20 = c.rolling(20, min_periods=20).mean()
    sma60 = c.rolling(60, min_periods=60).mean()
    f["d_sma20"] = (logc - np.log(sma20)) / volf
    f["d_sma60"] = (logc - np.log(sma60)) / volf
    f["rsi14"] = (_rsi(c, 14) - 50) / 50
    std20 = c.rolling(20, min_periods=20).std()
    f["boll_z"] = (c - sma20) / std20.where(std20 > 0)
    sp = bars["spread_c"]
    f["spread_vol"] = (sp / c) / volf
    sp_med = sp.rolling(240, min_periods=120).median()
    # Fuentes sin bid/ask (spread = 0, p. ej. Binance): spread relativo neutro = 1.
    f["spread_rel"] = (sp / sp_med.where(sp_med > 0)).where(sp_med > 0, 1.0).where(sp_med.notna())
    lv = np.log1p(bars["volume"])
    f["vol_rel"] = lv - lv.rolling(240, min_periods=120).mean()
    f["notick60"] = bars["no_tick"].astype(float).where(c.notna()).rolling(60, min_periods=50).mean()
    mod = (bars.index.hour * 60 + bars.index.minute).to_numpy()
    f["tod_sin"] = np.sin(2 * np.pi * mod / 1440)
    f["tod_cos"] = np.cos(2 * np.pi * mod / 1440)
    f["dow"] = bars.index.dayofweek.to_numpy().astype(float)
    # Horario programado del minuto siguiente (información de calendario fijo, no de precios).
    nxt = bars.index + pd.Timedelta(minutes=1)
    f["sched_next"] = in_release_window(nxt).astype(float)
    # Sin vela en t → sin decisión.
    f.loc[c.isna()] = np.nan
    return f[FEATURES].replace([np.inf, -np.inf], np.nan)


def rolling_abs_move(bars: pd.DataFrame, horizon: int, window: int = 1440) -> pd.Series:
    """Estimación causal del movimiento absoluto medio a horizonte h (para el EV de contado)."""
    c = bars["c"]
    mv = (c - c.shift(horizon)).abs()
    return mv.rolling(window, min_periods=window // 4).mean()
