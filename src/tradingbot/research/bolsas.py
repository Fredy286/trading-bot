"""Cierres de 1 min de otras criptomonedas en las bolsas en USDT que forman el precio de IQ Option (Estudio 47):
Binance, Bybit y OKX por sus API públicas y Gate por sus archivos diarios. Es la misma receta de los Estudios 41 y 47
(que solo descargaron BTC), con caché por mes en `data/raw/bolsas_usdt/<SÍMBOLO>/<bolsa>/<AAAA-MM>.parquet`.

Solo descarga hasta el 2026-10-26 00:05 (`study41.END`): lo posterior está reservado para confirmaciones.
"""

from __future__ import annotations

import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd
import requests

from .study41 import END, _get, _ms, pages
from .study47 import parse_gate

WORK = Path("data/raw/bolsas_usdt")
GATE_URL = "https://download.gatedata.org/spot/candlesticks_1m/{ym}/{pair}-{d}.csv.gz"
NOMBRES = {  # símbolo → nombre en cada bolsa
    "ETHUSDT": {"binance": "ETHUSDT", "bybit": "ETHUSDT", "okx": "ETH-USDT", "gate": "ETH_USDT"},
    "SOLUSDT": {"binance": "SOLUSDT", "bybit": "SOLUSDT", "okx": "SOL-USDT", "gate": "SOL_USDT"},
    "XRPUSDT": {"binance": "XRPUSDT", "bybit": "XRPUSDT", "okx": "XRP-USDT", "gate": "XRP_USDT"},
    "DOGEUSDT": {"binance": "DOGEUSDT", "bybit": "DOGEUSDT", "okx": "DOGE-USDT", "gate": "DOGE_USDT"},
    "LTCUSDT": {"binance": "LTCUSDT", "bybit": "LTCUSDT", "okx": "LTC-USDT", "gate": "LTC_USDT"},
}


def _binance(s, name, a, b):
    k = _get(s, "https://api.binance.com/api/v3/klines",
             {"symbol": name, "interval": "1m", "startTime": _ms(a), "endTime": _ms(b), "limit": 1000})
    return [(int(x[0]), float(x[4])) for x in k]


def _bybit(s, name, a, b):
    for intento in range(6):  # con límite de velocidad Bybit responde 200 con retCode ≠ 0 y sin «list»
        r = _get(s, "https://api.bybit.com/v5/market/kline",
                 {"category": "spot", "symbol": name, "interval": "1", "start": _ms(a), "end": _ms(b), "limit": 1000})
        if r.get("retCode") == 0 and "list" in r.get("result", {}):
            return [(int(x[0]), float(x[4])) for x in r["result"]["list"]]
        time.sleep(2 * (intento + 1))
    raise RuntimeError(f"Bybit no respondió bien: {r.get('retCode')} {r.get('retMsg')}")


def _okx(s, name, a, b):
    r = _get(s, "https://www.okx.com/api/v5/market/history-candles",
             {"instId": name, "bar": "1m", "after": _ms(b) + 1, "before": _ms(a) - 1, "limit": 100})
    return [(int(x[0]), float(x[4])) for x in r["data"]]


PAGE = {"binance": (_binance, 1000, 0.05), "bybit": (_bybit, 1000, 0.1), "okx": (_okx, 100, 0.11)}


def month_closes(symbol: str, venue: str, ym: str, work: Path = WORK, session=None, log=print) -> pd.Series:
    """Cierres de 1 min de `symbol` en `venue` durante el mes `ym` (caché por mes)."""
    f = Path(work) / symbol / venue / f"{ym}.parquet"
    if f.exists():
        return pd.read_parquet(f)["c"]
    s = session or requests.Session()
    name = NOMBRES[symbol][venue]
    start = pd.Timestamp(ym + "-01", tz="UTC")
    end = min(start + pd.offsets.MonthBegin(1), END)
    if venue == "gate":
        parts = []
        for d in pd.date_range(start, end.ceil("D"), freq="D", inclusive="left"):
            for intento in range(5):
                r = s.get(GATE_URL.format(ym=f"{d:%Y%m}", pair=name, d=f"{d:%Y%m%d}"), timeout=60)
                if r.status_code == 200:
                    parts.append(parse_gate(r.content))
                    break
                time.sleep(2 * (intento + 1))
            time.sleep(0.05)
        ser = pd.concat(parts).sort_index() if parts else pd.Series(dtype=float)
    else:
        fetch, size, pause = PAGE[venue]
        rows = []
        for a, b in pages(start, end, size):
            rows.extend(r for r in fetch(s, name, a, b) if _ms(a) <= r[0] <= _ms(b))
            time.sleep(pause)
        df = pd.DataFrame(rows, columns=["t", "c"]).drop_duplicates("t")
        ser = pd.Series(df["c"].to_numpy(), index=pd.to_datetime(df["t"], unit="ms", utc=True)).sort_index()
    ser = ser[~ser.index.duplicated(keep="last")]
    ser = ser[(ser.index >= start) & (ser.index < END)]
    f.parent.mkdir(parents=True, exist_ok=True)
    tmp = f.with_suffix(f".{uuid.uuid4().hex[:6]}.tmp")
    ser.to_frame("c").to_parquet(tmp)
    tmp.replace(f)  # nunca queda un archivo a medio escribir
    log(f"  {symbol} {venue} {ym}: {len(ser):,} velas")
    return ser


def download(symbol: str, first: str = "2024-08", last: str = "2026-10", gate_first: str = "2025-09",
             venues=("binance", "bybit", "okx", "gate"), workers: int = 1, log=print) -> None:
    """Descarga los meses que falten. Con `workers` > 1 baja varios meses a la vez (OKX entrega 100 velas por consulta
    y, de a una, tarda casi 4 min por mes; su límite es de 10 consultas por segundo)."""
    def one(job):
        v, ym = job
        try:
            month_closes(symbol, v, ym, session=requests.Session(), log=log)
        except (RuntimeError, requests.RequestException) as exc:
            log(f"  {symbol} {v} {ym}: falló ({type(exc).__name__}); se reintenta en la próxima ejecución")

    jobs = [(v, p.strftime("%Y-%m")) for v in venues
            for p in pd.period_range(gate_first if v == "gate" else first, last, freq="M")]
    if workers <= 1:
        for j in jobs:
            one(j)
        return
    with ThreadPoolExecutor(max_workers=workers) as ex:
        list(ex.map(one, jobs))
