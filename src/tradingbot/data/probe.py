"""Diagnóstico de acceso a fuentes de datos: qué responde cada URL desde ESTA máquina.

Uso: `tbot data probe`. Hace peticiones secuenciales (con pausa) y muestra código HTTP, tamaño y
cabeceras relevantes. No descarga volúmenes grandes.
"""

from __future__ import annotations

import time

import requests

from .http import USER_AGENT

BROWSER_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
              "Chrome/126.0 Safari/537.36")

PROBES = [
    ("dukascopy M1 día 2021-01-05", "https://datafeed.dukascopy.com/datafeed/EURUSD/2021/00/05/BID_candles_min_1.bi5"),
    ("dukascopy M1 día 2026-08-03", "https://datafeed.dukascopy.com/datafeed/EURUSD/2026/07/03/BID_candles_min_1.bi5"),
    ("dukascopy ticks hora 2021-01-05 10h", "https://datafeed.dukascopy.com/datafeed/EURUSD/2021/00/05/10h_ticks.bi5"),
    ("dukascopy H1 mes 2021-01", "https://datafeed.dukascopy.com/datafeed/EURUSD/2021/00/BID_candles_hour_1.bi5"),
    ("binance archivo mensual", "https://data.binance.vision/data/spot/monthly/klines/BTCUSDT/1m/BTCUSDT-1m-2024-01.zip"),
    ("binance API klines", "https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1m&limit=2"),
    ("histdata página", "https://www.histdata.com/download-free-forex-data/"),
    ("yahoo chart EURUSD=X 1m", "https://query1.finance.yahoo.com/v8/finance/chart/EURUSD=X?interval=1m&range=1d"),
    ("deriv sitio API", "https://api.deriv.com/"),
    ("forexfactory calendario semanal", "https://nfs.faireconomy.media/ff_calendar_thisweek.json"),
]


def run(pause_s: float = 1.5, timeout: float = 20.0) -> list[dict]:
    out = []
    for ua_name, ua in (("tradingbot", USER_AGENT), ("navegador", BROWSER_UA)):
        s = requests.Session()
        s.headers.update({"User-Agent": ua})
        for name, url in PROBES:
            t0 = time.time()
            try:
                r = s.get(url, timeout=timeout, stream=True)
                body = r.raw.read(4096, decode_content=False)
                row = {"ua": ua_name, "fuente": name, "status": r.status_code,
                       "bytes_leidos": len(body), "content_length": r.headers.get("Content-Length"),
                       "retry_after": r.headers.get("Retry-After"), "server": r.headers.get("Server"),
                       "segundos": round(time.time() - t0, 2)}
                r.close()
            except requests.RequestException as exc:
                row = {"ua": ua_name, "fuente": name, "status": None, "error": type(exc).__name__,
                       "segundos": round(time.time() - t0, 2)}
            out.append(row)
            print(row, flush=True)
            time.sleep(pause_s)
    return out
