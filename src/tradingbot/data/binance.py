"""Velas de 1 minuto de Binance (spot) desde los archivos públicos de data.binance.vision.

- URL mensual: https://data.binance.vision/data/spot/monthly/klines/{SIMBOLO}/1m/{SIMBOLO}-1m-{AAAA}-{MM}.zip
- Columnas: open_time, open, high, low, close, volume, close_time, quote_volume, trades,
  taker_buy_base, taker_buy_quote, ignore.
- Desde 2025-01-01 los archivos spot usan MICROsegundos en las marcas de tiempo (antes, milisegundos);
  se detecta por magnitud.
No hay bid/ask: el spread se toma como 0 y el costo se modela con la comisión (20 pb ida y vuelta).
"""

from __future__ import annotations

import io
import zipfile
from datetime import date

import numpy as np
import pandas as pd

from ..instruments import Instrument
from .dukascopy import validate_ohlc
from .http import NotFound, get_bytes, make_session

BASE_URL = "https://data.binance.vision/data/spot/monthly/klines"
KLINE_COLS = ["open_time", "open", "high", "low", "close", "volume", "close_time", "quote_volume",
              "trades", "taker_buy_base", "taker_buy_quote", "ignore"]


def month_url(symbol: str, year: int, month: int) -> str:
    s = symbol.upper()
    return f"{BASE_URL}/{s}/1m/{s}-1m-{year:04d}-{month:02d}.zip"


def parse_klines_csv(raw_csv: bytes, inst: Instrument) -> pd.DataFrame:
    df = pd.read_csv(io.BytesIO(raw_csv), header=None, names=KLINE_COLS)
    if not str(df.iloc[0, 0]).strip().lstrip("-").isdigit():  # archivo con cabecera
        df = df.iloc[1:].copy()
    ot = pd.to_numeric(df["open_time"]).astype(np.int64)
    unit = "us" if ot.max() > 10**14 else "ms"
    idx = pd.to_datetime(ot, unit=unit, utc=True)
    out = pd.DataFrame(
        {
            "o": pd.to_numeric(df["open"]).to_numpy(float),
            "h": pd.to_numeric(df["high"]).to_numpy(float),
            "l": pd.to_numeric(df["low"]).to_numpy(float),
            "c": pd.to_numeric(df["close"]).to_numpy(float),
            "v": pd.to_numeric(df["volume"]).to_numpy(float),
            "trades": pd.to_numeric(df["trades"]).to_numpy(float),
        },
        index=pd.DatetimeIndex(idx, name="time"),
    )
    validate_ohlc(out, inst, context=f"{inst.symbol} binance")
    # Formato canónico: bid = ask = precio negociado.
    canon = pd.DataFrame(index=out.index)
    for side in ("bid", "ask"):
        for k in ("o", "h", "l", "c"):
            canon[f"{side}_{k}"] = out[k]
    canon["bid_v"] = out["v"]
    canon["ask_v"] = 0.0
    canon["trades"] = out["trades"]
    return canon


DAILY_URL = "https://data.binance.vision/data/spot/daily/klines"


def day_url(symbol: str, day: date, interval: str = "1m") -> str:
    s = symbol.upper()
    return f"{DAILY_URL}/{s}/{interval}/{s}-{interval}-{day:%Y-%m-%d}.zip"


def parse_closes_csv(raw_csv: bytes) -> pd.Series:
    """Velas de 1 s: solo el cierre (último precio negociado de cada segundo), indexado por la apertura."""
    df = pd.read_csv(io.BytesIO(raw_csv), header=None, usecols=[0, 4], names=["open_time", "close"])
    if not str(df.iloc[0, 0]).strip().lstrip("-").isdigit():
        df = df.iloc[1:]
    ot = pd.to_numeric(df["open_time"]).astype(np.int64)
    unit = "us" if ot.max() > 10**14 else "ms"
    return pd.Series(pd.to_numeric(df["close"]).to_numpy(float),
                     index=pd.DatetimeIndex(pd.to_datetime(ot, unit=unit, utc=True), name="time"), name="c")


def download_days(inst: Instrument, start: date, end: date, interval: str = "1m", cache_dir=None,
                  progress: bool = True):
    """Archivos DIARIOS (antes de que Binance publique el mensual), con caché en disco.

    interval «1m» → velas en formato canónico (como `download`); «1s» → serie de cierres por segundo.
    """
    from pathlib import Path

    session = make_session()
    cache = Path(cache_dir) / inst.symbol / interval if cache_dir else None
    parts = []
    day = start
    while day < end:
        f = cache / f"{day:%Y-%m-%d}.parquet" if cache else None
        if f is not None and f.exists():
            part = pd.read_parquet(f)
        else:
            try:
                raw = get_bytes(session, day_url(inst.symbol, day, interval), timeout=120)
            except NotFound:
                print(f"  {inst.symbol} {interval}: {day} no disponible (404)", flush=True)
                day += pd.Timedelta(days=1).to_pytimedelta()
                continue
            with zipfile.ZipFile(io.BytesIO(raw)) as zf:
                csv = zf.read(zf.namelist()[0])
            part = parse_klines_csv(csv, inst) if interval == "1m" else parse_closes_csv(csv).to_frame()
            if f is not None:
                f.parent.mkdir(parents=True, exist_ok=True)
                part.to_parquet(f)
            if progress:
                print(f"  {inst.symbol} {interval}: {day} OK", flush=True)
        parts.append(part)
        day += pd.Timedelta(days=1).to_pytimedelta()
    if not parts:
        return pd.DataFrame() if interval == "1m" else pd.Series(dtype=float, name="c")
    out = pd.concat(parts).sort_index()
    out = out[~out.index.duplicated(keep="last")]
    return out if interval == "1m" else out["c"]


def download(inst: Instrument, start: date, end: date, progress: bool = True) -> pd.DataFrame:
    session = make_session()
    frames = []
    y, m = start.year, start.month
    while date(y, m, 1) < end:
        url = month_url(inst.symbol, y, m)
        try:
            raw = get_bytes(session, url, timeout=120)
            with zipfile.ZipFile(io.BytesIO(raw)) as zf:
                name = zf.namelist()[0]
                frames.append(parse_klines_csv(zf.read(name), inst))
            if progress:
                print(f"  {inst.symbol}: {y}-{m:02d} OK", flush=True)
        except NotFound:
            print(f"  {inst.symbol}: {y}-{m:02d} no disponible (404)", flush=True)
        m += 1
        if m == 13:
            y, m = y + 1, 1
    if not frames:
        return pd.DataFrame()
    out = pd.concat(frames).sort_index()
    out = out[~out.index.duplicated(keep="last")]
    start_ts = pd.Timestamp(start, tz="UTC")
    end_ts = pd.Timestamp(end, tz="UTC")
    return out[(out.index >= start_ts) & (out.index < end_ts)]
