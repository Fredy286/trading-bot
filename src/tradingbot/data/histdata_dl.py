"""Descarga automática desde HistData.com (M1, «Generic ASCII», precio BID, EST fija UTC−5).

HistData no ofrece API oficial: el sitio entrega un token (`tk`) en la página de descarga y el ZIP
se obtiene con un POST a get.php indicando esa página como Referer (flujo usado por el paquete
abierto `histdata`). Años pasados: un ZIP por año; año en curso: un ZIP por mes.
"""

from __future__ import annotations

import io
import re
import zipfile
from datetime import date

import pandas as pd

from ..instruments import Instrument
from .histdata import parse_ascii_m1
from .http import make_session

PAGE = "https://www.histdata.com/download-free-forex-historical-data/?/ascii/1-minute-bar-quotes/{pair}/{period}"
POST = "https://www.histdata.com/get.php"
TOKEN_RE = re.compile(r'id="tk"[^>]*value="([^"]+)"|value="([^"]+)"[^>]*id="tk"')


class HistDataError(Exception):
    pass


def extract_token(html: str) -> str:
    m = TOKEN_RE.search(html)
    if not m:
        raise HistDataError("No se encontró el token de descarga (¿cambió el sitio o el par/año no existe?)")
    return m.group(1) or m.group(2)


def fetch_zip(session, pair: str, year: int, month: int | None) -> bytes:
    period = f"{year}/{month}" if month else f"{year}"
    page = PAGE.format(pair=pair.lower(), period=period)
    r = session.get(page, timeout=60)
    r.raise_for_status()
    tk = extract_token(r.text)
    data = {"tk": tk, "date": str(year), "datemonth": f"{year}{month:02d}" if month else str(year),
            "platform": "ASCII", "timeframe": "M1", "fxpair": pair.upper()}
    resp = session.post(POST, data=data, headers={"Referer": page, "Origin": "https://www.histdata.com"}, timeout=180)
    resp.raise_for_status()
    if not resp.content.startswith(b"PK"):
        raise HistDataError(f"Respuesta inesperada de HistData para {pair} {period} (no es un ZIP)")
    return resp.content


def download(inst: Instrument, start: date, end: date, assumed_spread: float, progress: bool = True) -> pd.DataFrame:
    session = make_session()
    frames = []
    today = date.today()
    for year in range(start.year, end.year + 1):
        months = [None] if year < today.year else list(range(1, 13))
        for m in months:
            if m and date(year, m, 1) >= min(end, today):
                break
            blob = fetch_zip(session, inst.symbol, year, m)
            with zipfile.ZipFile(io.BytesIO(blob)) as zf:
                name = next(n for n in zf.namelist() if n.lower().endswith(".csv"))
                frames.append(parse_ascii_m1(zf.read(name), inst, assumed_spread))
            if progress:
                print(f"  {inst.symbol}: HistData {year}{'-%02d' % m if m else ''} OK", flush=True)
    if not frames:
        return pd.DataFrame()
    out = pd.concat(frames).sort_index()
    out = out[~out.index.duplicated(keep="last")]
    return out[(out.index >= pd.Timestamp(start, tz="UTC")) & (out.index < pd.Timestamp(end, tz="UTC"))]
