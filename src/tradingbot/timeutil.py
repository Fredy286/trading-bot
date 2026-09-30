"""Utilidades de tiempo. Todo se almacena en UTC; se muestra en America/Bogota."""

from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pandas as pd

UTC = timezone.utc
BOGOTA = ZoneInfo("America/Bogota")


def utcnow() -> datetime:
    return datetime.now(UTC)


def to_bogota(ts: datetime | pd.Timestamp) -> datetime:
    """Convierte una marca temporal (con zona) a America/Bogota."""
    if isinstance(ts, pd.Timestamp):
        ts = ts.to_pydatetime()
    if ts.tzinfo is None:
        raise ValueError("Marca temporal sin zona horaria: se exige UTC explícito.")
    return ts.astimezone(BOGOTA)


def fmt_bogota(ts: datetime | pd.Timestamp | None, with_seconds: bool = True) -> str:
    if ts is None:
        return "—"
    fmt = "%Y-%m-%d %H:%M:%S" if with_seconds else "%Y-%m-%d %H:%M"
    return to_bogota(ts).strftime(fmt) + " America/Bogota"


def ensure_utc_index(df: pd.DataFrame) -> pd.DataFrame:
    """Verifica que el índice sea DatetimeIndex en UTC, ordenado y sin duplicados."""
    if not isinstance(df.index, pd.DatetimeIndex):
        raise TypeError("El índice debe ser DatetimeIndex.")
    if df.index.tz is None:
        raise ValueError("El índice no tiene zona horaria; se exige UTC.")
    if str(df.index.tz) != "UTC":
        df = df.tz_convert("UTC")
    if not df.index.is_monotonic_increasing:
        df = df.sort_index()
    if df.index.has_duplicates:
        df = df[~df.index.duplicated(keep="last")]
    return df
