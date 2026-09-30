"""Almacenamiento reproducible en Parquet (un archivo por instrumento y año) con manifiesto.

El manifiesto registra: fuente, patrón de URL, rango, filas, huella SHA-256, fecha de descarga (UTC),
zona horaria de los datos y la regla de disponibilidad (cuándo habría estado disponible cada vela).
"""

from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path

import pandas as pd

from .. import __version__
from ..instruments import Instrument
from ..timeutil import utcnow

AVAILABILITY_RULE = (
    "Una vela con marca t (inicio del minuto, UTC) se considera disponible en t + 60 s + latencia del "
    "proveedor. En históricos la latencia se supone (parámetro feed_latency_s); en vivo se registra la "
    "hora real de recepción (received_at)."
)

SOURCE_URLS = {
    "dukascopy": "https://datafeed.dukascopy.com/datafeed/{SYM}/{YYYY}/{MM0}/{DD}/{BID|ASK}_candles_min_1.bi5",
    "binance": "https://data.binance.vision/data/spot/monthly/klines/{SYM}/1m/{SYM}-1m-{YYYY}-{MM}.zip",
    "histdata": "https://www.histdata.com (ASCII M1, BID, EST fija; POST get.php con token)",
    "synthetic": "generado localmente (NO son datos de mercado)",
}


def symbol_dir(root: Path, inst: Instrument, source: str | None = None) -> Path:
    return Path(root) / (source or inst.source) / inst.symbol


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_manifest(root: Path, inst: Instrument, source: str | None = None) -> dict:
    p = symbol_dir(root, inst, source) / "manifest.json"
    return json.loads(p.read_text()) if p.exists() else {"years": {}}


def write_year(df: pd.DataFrame, root: Path, inst: Instrument, year: int, start: date, end: date,
               source: str | None = None) -> Path:
    source = source or inst.source
    d = symbol_dir(root, inst, source)
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{year}.parquet"
    df.to_parquet(path, compression="zstd")
    man = read_manifest(root, inst, source)
    man.update({
        "symbol": inst.symbol,
        "source": source,
        "source_url_pattern": SOURCE_URLS.get(source, ""),
        "timezone": "UTC",
        "availability_rule": AVAILABILITY_RULE,
    })
    man["years"][str(year)] = {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "rows": int(len(df)),
        "first": df.index.min().isoformat() if len(df) else None,
        "last": df.index.max().isoformat() if len(df) else None,
        "sha256": _sha256(path),
        "retrieved_at_utc": utcnow().isoformat(),
        "code_version": __version__,
    }
    (d / "manifest.json").write_text(json.dumps(man, indent=2, ensure_ascii=False))
    return path


def ensure_downloaded(inst: Instrument, start: date, end: date, root: Path, workers: int = 8,
                      source: str | None = None) -> None:
    """Descarga por años lo que falte (idempotente: reutiliza lo ya descargado)."""
    from . import binance, dukascopy, histdata_dl

    source = source or inst.source
    man = read_manifest(root, inst, source)
    for year in range(start.year, end.year + 1):
        ys, ye = max(start, date(year, 1, 1)), min(end, date(year + 1, 1, 1))
        if ys >= ye:
            continue
        prev = man["years"].get(str(year))
        path = symbol_dir(root, inst, source) / f"{year}.parquet"
        if prev and path.exists() and prev["start"] <= ys.isoformat() and prev["end"] >= ye.isoformat():
            print(f"{inst.symbol} {year}: ya descargado ({prev['rows']} filas)", flush=True)
            continue
        print(f"{inst.symbol} {year}: descargando {ys} → {ye} desde {source}", flush=True)
        if source == "dukascopy":
            df = dukascopy.download(inst, ys, ye, workers=workers)
        elif source == "binance":
            df = binance.download(inst, ys, ye)
        elif source == "histdata":
            df = histdata_dl.download(inst, ys, ye, assumed_spread=inst.assumed_spread)
        else:
            raise ValueError(f"Fuente sin descargador automático: {source}")
        if df.empty:
            print(f"{inst.symbol} {year}: SIN DATOS", flush=True)
            continue
        write_year(df, root, inst, year, ys, ye, source)
        man = read_manifest(root, inst, source)


def load(root: Path, inst: Instrument, start: pd.Timestamp | None = None,
         end: pd.Timestamp | None = None, source: str | None = None) -> pd.DataFrame:
    d = symbol_dir(root, inst, source)
    files = sorted(d.glob("*.parquet"))
    if not files:
        raise FileNotFoundError(f"No hay datos en {d}. Ejecute: tbot data download --symbols {inst.symbol}"
                                f"{' --source ' + source if source else ''}")
    df = pd.concat([pd.read_parquet(f) for f in files]).sort_index()
    df = df[~df.index.duplicated(keep="last")]
    if start is not None:
        df = df[df.index >= start]
    if end is not None:
        df = df[df.index < end]
    return df
