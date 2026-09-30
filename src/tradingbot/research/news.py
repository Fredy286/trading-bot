"""Noticias: ventanas de publicación PROGRAMADAS (conocidas de antemano) y calendario importable.

En el backtest NO se usa un calendario real (no hay histórico gratuito con hora de publicación y
consenso fiables): se usan horas típicas de publicación, aplicadas todos los días hábiles. Eso no
introduce información futura porque el horario es público y fijo.
En vivo se puede cargar un CSV de calendario con la hora de publicación de cada evento y la hora en
que el sistema lo tuvo disponible (`available_at`).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# (zona horaria, hora, minuto): horas típicas de publicación. Ver protocolo, sección 3.
SCHEDULED_RELEASES: list[tuple[str, int, int]] = [
    ("America/New_York", 8, 30),
    ("America/New_York", 10, 0),
    ("America/New_York", 14, 0),
    ("Europe/London", 7, 0),
    ("Europe/London", 9, 30),
    ("Europe/Berlin", 14, 15),
    ("Australia/Sydney", 11, 30),
    ("Asia/Tokyo", 8, 50),
]


def in_release_window(index: pd.DatetimeIndex, before_min: int = 5, after_min: int = 10) -> np.ndarray:
    """True si el minuto cae entre `before_min` antes y `after_min` después de una hora de publicación."""
    mask = np.zeros(len(index), dtype=bool)
    for tz, hh, mm in SCHEDULED_RELEASES:
        local = index.tz_convert(tz)
        mod = (local.hour * 60 + local.minute).to_numpy()
        rel = hh * 60 + mm
        weekday = (local.dayofweek < 5)
        mask |= weekday & (mod >= rel - before_min) & (mod < rel + after_min)
    return mask


def trade_overlaps_window(index: pd.DatetimeIndex, entry_delay: int, horizon: int,
                          before_min: int = 5, after_min: int = 10) -> np.ndarray:
    """True si la vela de decisión o cualquier vela de la operación cae en una ventana programada.

    `index` debe ser una rejilla regular de minutos (se usa el horario, no precios).
    """
    w = pd.Series(in_release_window(index, before_min, after_min).astype(np.int8), index=index)
    n_fwd = entry_delay + horizon - 1
    fwd = w.rolling(horizon, min_periods=1).max().shift(-n_fwd).fillna(1)
    return (w.to_numpy() > 0) | (fwd.to_numpy() > 0)


def load_calendar_csv(path) -> pd.DataFrame:
    """CSV con columnas: event_time_utc, currency, impact, title[, available_at_utc].

    `event_time_utc` es la hora programada de publicación; `available_at_utc` la hora en que el
    sistema recibió el registro (si falta, se asume desconocida y se registra como NaT).
    """
    df = pd.read_csv(path)
    required = {"event_time_utc", "currency", "impact", "title"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Faltan columnas en el calendario: {sorted(missing)}")
    df["event_time_utc"] = pd.to_datetime(df["event_time_utc"], utc=True)
    if "available_at_utc" in df:
        df["available_at_utc"] = pd.to_datetime(df["available_at_utc"], utc=True)
    else:
        df["available_at_utc"] = pd.NaT
    df["impact"] = df["impact"].str.lower()
    return df.sort_values("event_time_utc").reset_index(drop=True)


def calendar_blackout(now_utc: pd.Timestamp, horizon_min: int, events: pd.DataFrame, currencies: set[str],
                      before_min: int = 5, after_min: int = 10, impacts=("high",)) -> pd.DataFrame:
    """Eventos del calendario que invalidan una operación que empieza ahora y dura `horizon_min`.

    Solo se consideran eventos cuyo registro estaba disponible antes de `now_utc` (si se conoce).
    """
    if events is None or events.empty:
        return pd.DataFrame()
    start = now_utc - pd.Timedelta(minutes=after_min)
    end = now_utc + pd.Timedelta(minutes=horizon_min + before_min)
    e = events[(events["event_time_utc"] >= start) & (events["event_time_utc"] <= end)]
    e = e[e["impact"].isin(impacts) & e["currency"].str.upper().isin({c.upper() for c in currencies})]
    known = e["available_at_utc"].isna() | (e["available_at_utc"] <= now_utc)
    return e[known]
