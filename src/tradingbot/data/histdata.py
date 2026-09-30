"""Importador de archivos locales de HistData.com (formato «Generic ASCII», 1 minuto).

HistData no tiene API oficial: el usuario descarga los ZIP manualmente desde histdata.com.
Formato: `AAAAMMDD HHMMSS;apertura;máximo;mínimo;cierre;volumen`, precios BID, zona horaria
EST **sin** horario de verano (UTC−5 fija). No trae ASK: el spread se debe suponer (parámetro).
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pandas as pd

from ..instruments import Instrument
from .dukascopy import validate_ohlc


def parse_ascii_m1(text: str | bytes, inst: Instrument, assumed_spread: float) -> pd.DataFrame:
    if isinstance(text, bytes):
        text = text.decode("utf-8", errors="replace")
    df = pd.read_csv(io.StringIO(text), sep=";", header=None, names=["dt", "o", "h", "l", "c", "v"])
    idx = pd.to_datetime(df["dt"], format="%Y%m%d %H%M%S") + pd.Timedelta(hours=5)  # EST fijo → UTC
    bid = pd.DataFrame({k: df[k].to_numpy(float) for k in ("o", "h", "l", "c")},
                       index=pd.DatetimeIndex(idx, name="time").tz_localize("UTC"))
    validate_ohlc(bid.assign(v=0.0), inst, context=f"{inst.symbol} histdata")
    out = bid.add_prefix("bid_")
    for k in ("o", "h", "l", "c"):
        out[f"ask_{k}"] = out[f"bid_{k}"] + assumed_spread
    out["bid_v"] = df["v"].to_numpy(float)
    out["ask_v"] = 0.0
    return out.sort_index()


def load_path(path: str | Path, inst: Instrument, assumed_spread: float) -> pd.DataFrame:
    path = Path(path)
    if path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as zf:
            name = next(n for n in zf.namelist() if n.lower().endswith(".csv"))
            return parse_ascii_m1(zf.read(name), inst, assumed_spread)
    return parse_ascii_m1(path.read_bytes(), inst, assumed_spread)
