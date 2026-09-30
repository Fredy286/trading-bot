"""Cliente HTTP con reintentos y retroceso exponencial (compartido por los descargadores)."""

from __future__ import annotations

import time

import requests

USER_AGENT = "tradingbot-research/0.1 (+https://github.com/Fredy286/trading-bot)"


class NotFound(Exception):
    """El recurso no existe (404) o está vacío."""


def make_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": USER_AGENT})
    adapter = requests.adapters.HTTPAdapter(pool_connections=32, pool_maxsize=32)
    s.mount("https://", adapter)
    return s


def get_bytes(session: requests.Session, url: str, retries: int = 5, timeout: float = 30.0) -> bytes:
    """Descarga bytes. Lanza NotFound en 404; reintenta en errores transitorios (5xx, 429, red)."""
    delay = 2.0
    last_exc: Exception | None = None
    for _ in range(retries):
        try:
            resp = session.get(url, timeout=timeout)
            if resp.status_code == 404:
                raise NotFound(url)
            if resp.status_code in (429, 500, 502, 503, 504):
                last_exc = RuntimeError(f"HTTP {resp.status_code} en {url}")
            else:
                resp.raise_for_status()
                return resp.content
        except NotFound:
            raise
        except requests.RequestException as exc:  # errores de red
            last_exc = exc
        time.sleep(delay)
        delay = min(delay * 2, 30.0)
    raise RuntimeError(f"No se pudo descargar {url} tras {retries} intentos: {last_exc}")
