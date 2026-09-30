"""Descargador de velas de 1 minuto BID y ASK del datafeed público de Dukascopy Bank SA.

Formato (ingeniería inversa ampliamente documentada por herramientas abiertas como dukascopy-node):
- URL diaria: https://datafeed.dukascopy.com/datafeed/{SIMBOLO}/{AAAA}/{MM-1:02d}/{DD:02d}/{BID|ASK}_candles_min_1.bi5
  (¡el mes empieza en 00!).
- Contenido comprimido LZMA; registros de 24 bytes big-endian:
  segundos desde 00:00 UTC del día (u4), apertura (u4), cierre (u4), mínimo (u4), máximo (u4), volumen (f4).
- Precio = entero / factor decimal (100000 para la mayoría de pares, 1000 para JPY y oro).

Como el formato no es oficial, la decodificación se valida SIEMPRE (orden OHLC coherente y rango
plausible). Si la validación falla, se lanza DecodeError en lugar de producir datos erróneos.
"""

from __future__ import annotations

import lzma
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

import numpy as np
import pandas as pd

from ..instruments import Instrument
from .http import NotFound, get_bytes, make_session

BASE_URL = "https://datafeed.dukascopy.com/datafeed"

CANDLE_DTYPE = np.dtype(
    [("t", ">u4"), ("o", ">u4"), ("c", ">u4"), ("l", ">u4"), ("h", ">u4"), ("v", ">f4")]
)


class DecodeError(Exception):
    pass


def day_url(symbol: str, day: date, side: str) -> str:
    side = side.upper()
    if side not in ("BID", "ASK"):
        raise ValueError("side debe ser BID o ASK")
    return f"{BASE_URL}/{symbol.upper()}/{day.year:04d}/{day.month - 1:02d}/{day.day:02d}/{side}_candles_min_1.bi5"


def decode_candles(raw: bytes, day: date, inst: Instrument) -> pd.DataFrame:
    """Decodifica un archivo .bi5 de velas M1 y devuelve un DataFrame indexado en UTC."""
    cols = ["o", "h", "l", "c", "v"]
    if not raw:
        return pd.DataFrame(columns=cols, index=pd.DatetimeIndex([], tz="UTC", name="time"), dtype=float)
    data = lzma.decompress(raw)
    if len(data) % CANDLE_DTYPE.itemsize != 0:
        raise DecodeError(f"Tamaño {len(data)} no múltiplo de {CANDLE_DTYPE.itemsize}")
    arr = np.frombuffer(data, dtype=CANDLE_DTYPE)
    base = pd.Timestamp(day, tz="UTC")
    idx = base + pd.to_timedelta(arr["t"].astype(np.int64), unit="s")
    f = float(inst.decimal_factor)
    df = pd.DataFrame(
        {
            "o": arr["o"].astype(np.float64) / f,
            "h": arr["h"].astype(np.float64) / f,
            "l": arr["l"].astype(np.float64) / f,
            "c": arr["c"].astype(np.float64) / f,
            "v": arr["v"].astype(np.float64),
        },
        index=pd.DatetimeIndex(idx, name="time"),
    )
    validate_ohlc(df, inst, context=f"{inst.symbol} {day}")
    return df


def validate_ohlc(df: pd.DataFrame, inst: Instrument, context: str = "") -> None:
    """Controles de cordura: si fallan, el formato o el factor decimal son incorrectos."""
    if df.empty:
        return
    lo, hi = inst.plausible_range
    px = df[["o", "h", "l", "c"]].to_numpy()
    if np.nanmin(px) < lo * 0.5 or np.nanmax(px) > hi * 2:
        raise DecodeError(f"{context}: precios fuera de rango plausible [{lo}, {hi}]: "
                          f"{np.nanmin(px):.5f}..{np.nanmax(px):.5f}")
    tol = inst.point * 0.5
    bad = (df["l"] > df[["o", "c"]].min(axis=1) + tol) | (df["h"] < df[["o", "c"]].max(axis=1) - tol)
    if bad.mean() > 0.001:
        raise DecodeError(f"{context}: {bad.mean():.2%} de velas con OHLC incoherente (¿orden de campos?)")


def fetch_day(session, inst: Instrument, day: date) -> pd.DataFrame:
    """Descarga BID y ASK de un día y los combina en un solo DataFrame."""
    parts = {}
    for side in ("BID", "ASK"):
        try:
            raw = get_bytes(session, day_url(inst.symbol, day, side))
        except NotFound:
            raw = b""
        parts[side] = decode_candles(raw, day, inst)
    bid, ask = parts["BID"], parts["ASK"]
    if bid.empty and ask.empty:
        return pd.DataFrame()
    df = bid.add_prefix("bid_").join(ask.add_prefix("ask_"), how="outer")
    return df


def iter_days(start: date, end: date, skip_saturday: bool = True):
    d = start
    while d < end:
        if not (skip_saturday and d.weekday() == 5):
            yield d
        d += timedelta(days=1)


def download(inst: Instrument, start: date, end: date, workers: int = 8, progress: bool = True) -> pd.DataFrame:
    """Descarga el rango [start, end) y devuelve velas combinadas BID/ASK en UTC."""
    session = make_session()
    days = list(iter_days(start, end))
    frames: list[pd.DataFrame] = []
    done = 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for df in ex.map(lambda d: fetch_day(session, inst, d), days):
            done += 1
            if not df.empty:
                frames.append(df)
            if progress and done % 50 == 0:
                print(f"  {inst.symbol}: {done}/{len(days)} días descargados", flush=True)
    if not frames:
        return pd.DataFrame()
    out = pd.concat(frames).sort_index()
    out = out[~out.index.duplicated(keep="last")]
    return out
