"""Grabador del libro de órdenes de los «event contracts» de OKX de 5 min (ETH y BTC), para el Estudio 56.

Antes de cada ventana de 5 min guarda el libro del contrato de esa ventana 10, 7, 5 y 3 s antes de que empiece. El aviso
del bot sale 10 s antes, y el usuario tiene hasta 3 s antes, porque 1–2 s antes OKX retira los precios (docs/03, 2.3).
OKX no publica la historia del libro: solo se puede medir grabándolo en vivo. Lo corre
`.github/workflows/libro_okx.yml` cada 6 horas, y cada ejecución deja su propio archivo en `results/okx_libro/`.

Solo usa la API pública (sin cuenta), la biblioteca estándar y `requests`, para que el flujo de GitHub no tenga que
instalar todo el paquete. No envía órdenes.

Cada línea del archivo es una ventana:
    {"ventana": "2026-11-09T00:05:00Z", "fuente": "github",
     "ETHUSDT": {"inst": "ETH-UPDOWN-5MIN-261109-0805-0810",
                 "fotos": [{"seg": -10, "t": "...", "a": [[0.52, 13.1], ...], "b": [[0.48, 13.1], ...]}, ...]},
     "BTCUSDT": {...}}
«a» son las ventas de «Al alza» (precio, contratos) de menor a mayor precio. «b» son las compras: comprar «A la baja»
cuesta 1 − b. Si una foto falla, lleva «error» en lugar de «a» y «b».
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

OKX = "https://www.okx.com"
SERIES = {"ETHUSDT": "ETH-UPDOWN-5MIN", "BTCUSDT": "BTC-UPDOWN-5MIN"}
DUR_MIN = 5
FOTOS_S = (-10, -7, -5, -3)  # segundos respecto al inicio de la ventana
NIVELES = 5
UTC8 = timezone(timedelta(hours=8))
SALIDA = Path("results/okx_libro")


def inst_id(symbol: str, ventana: datetime, dur: int = DUR_MIN) -> str:
    """Nombre del contrato en OKX: fecha y horas en UTC+8 (igual que `okx_eventos.inst_id`)."""
    a = ventana.astimezone(UTC8)
    return f"{SERIES[symbol]}-{a:%y%m%d}-{a:%H%M}-{a + timedelta(minutes=dur):%H%M}"


def proxima_ventana(t: datetime, dur: int = DUR_MIN) -> datetime:
    """Primer inicio de ventana (múltiplo de `dur` min en UTC) que llega en `t` o después."""
    base = t.astimezone(timezone.utc).replace(second=0, microsecond=0)
    base -= timedelta(minutes=base.minute % dur)
    return base if base >= t else base + timedelta(minutes=dur)


def libro(session, inst: str, niveles: int = NIVELES) -> dict:
    """Mejores `niveles` precios de venta («a») y de compra («b») de «Al alza» del contrato `inst`."""
    r = session.get(OKX + "/api/v5/market/books", params={"instId": inst, "sz": niveles}, timeout=5)
    r.raise_for_status()
    j = r.json()
    if str(j.get("code")) != "0":
        return {"error": f"{j.get('code')} {j.get('msg')}"[:160]}
    d = (j.get("data") or [{}])[0]

    def par(xs):
        return [[float(x[0]), float(x[1])] for x in (xs or [])[:niveles]]

    return {"a": par(d.get("asks")), "b": par(d.get("bids"))}


def desfase_s(session, ahora=None) -> float:
    """Reloj de OKX menos el reloj local, en segundos (API pública `public/time`)."""
    ahora = ahora or (lambda: datetime.now(timezone.utc))
    t0 = ahora().timestamp()
    j = session.get(OKX + "/api/v5/public/time", timeout=5).json()
    t1 = ahora().timestamp()
    return int(j["data"][0]["ts"]) / 1000 - (t0 + t1) / 2


def _iso(t: datetime) -> str:
    return t.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def grabar(horas: float, salida: Path = SALIDA, fuente: str = "local", session=None, ahora=None, dormir=time.sleep,
           log=print) -> Path:
    """Graba el libro de cada ventana durante `horas` y devuelve el archivo. `ahora` y `dormir` se cambian en pruebas."""
    session = session or requests.Session()
    ahora = ahora or (lambda: datetime.now(timezone.utc))
    try:
        off = timedelta(seconds=desfase_s(session, ahora))
    except (requests.RequestException, ValueError, KeyError, IndexError) as exc:
        off = timedelta(0)
        log(f"Sin hora de OKX ({type(exc).__name__}); se usa el reloj local")
    inicio = ahora() + off
    fin = inicio + timedelta(hours=horas)
    salida = Path(salida)
    salida.mkdir(parents=True, exist_ok=True)
    archivo = salida / f"{inicio:%Y-%m-%d_%H%M}.jsonl"
    n, ultimo_ajuste = 0, inicio
    log(f"Grabando el libro de {', '.join(SERIES)} hasta {_iso(fin)} en {archivo}")
    while True:
        ventana = proxima_ventana(ahora() + off - timedelta(seconds=FOTOS_S[0]))
        if ventana + timedelta(seconds=FOTOS_S[-1]) > fin:
            break
        fila = {"ventana": _iso(ventana), "fuente": fuente,
                **{s: {"inst": inst_id(s, ventana), "fotos": []} for s in SERIES}}
        for seg in FOTOS_S:
            espera = (ventana + timedelta(seconds=seg) - (ahora() + off)).total_seconds()
            if espera > 0:
                dormir(espera)
            for s in SERIES:
                try:
                    foto = libro(session, fila[s]["inst"])
                except (requests.RequestException, ValueError, KeyError, IndexError) as exc:
                    foto = {"error": f"{type(exc).__name__}: {exc}"[:160]}
                fila[s]["fotos"].append({"seg": seg, "t": _iso(ahora() + off), **foto})
        with archivo.open("a", encoding="utf-8") as f:
            f.write(json.dumps(fila, ensure_ascii=False) + "\n")
        n += 1
        if ahora() + off - ultimo_ajuste > timedelta(hours=1):  # el reloj del equipo puede derivar
            try:
                off = timedelta(seconds=desfase_s(session, ahora))
            except (requests.RequestException, ValueError, KeyError, IndexError):
                pass
            ultimo_ajuste = ahora() + off
    log(f"{n} ventanas grabadas en {archivo}")
    return archivo


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Graba el libro de los event contracts de OKX de 5 min (Estudio 56).")
    p.add_argument("--horas", type=float, default=5.7)
    p.add_argument("--salida", default=str(SALIDA))
    p.add_argument("--fuente", default="local", help="«github» en el flujo de GitHub; el Estudio 56 usa solo esas")
    a = p.parse_args(argv)
    grabar(a.horas, Path(a.salida), a.fuente)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
