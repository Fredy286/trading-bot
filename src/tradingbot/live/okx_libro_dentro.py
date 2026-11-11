"""Grabador del libro de OKX DENTRO de cada ventana (5 y 15 min; ETH, BTC y SOL), para estudiar estrategias que se
operan con la ventana ya empezada.

Por qué: en Polymarket (marzo–mayo de 2026, exploración *post hoc* del 2026-11-10) el lado que va ganando a mitad de la
ventana gana más veces de lo que dice su precio (sesgo del favorito). Si OKX también lo tiene, sería una estrategia mucho
más fácil a mano que comprar en los 7 s antes del inicio. Para probarlo en OKX hay que grabar su libro dentro de la
ventana: OKX no publica esa historia.

Qué graba (API pública, sin cuenta; no envía órdenes):
- contratos de 5 min: en los segundos 60, 150 y 240, y 15 s antes del vencimiento (285);
- contratos de 15 min: en los segundos 120, 300, 480, 660 y 840, y 15 s antes del vencimiento (885);
- en cada foto: 3 niveles de compra y venta de «Al alza» y el precio del índice de OKX en ese momento;
- cada 5 min, los resultados oficiales de los contratos ya vencidos (partida, liquidación y resultado), porque OKX
  los guarda pocos días.

Corre en paralelo con el grabador del Estudio 56 (`okx_libro.py`) en el mismo flujo de GitHub, con archivos aparte en
`results/okx_dentro/`. Si falla, no afecta a aquel.
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

OKX = "https://www.okx.com"
MONEDAS = {"BTCUSDT": ("BTC", "BTC-USDT"), "ETHUSDT": ("ETH", "ETH-USDT"), "SOLUSDT": ("SOL", "SOL-USDT")}
# segundos desde el inicio de la ventana (pocas fotos: la primera prueba, 2026-11-11, mostró el libro casi vacío
# dentro de la ventana, 0,97/0,03 en BTC; se mide unos días antes de decidir si vale la pena seguir)
FOTOS = {5: (60, 150, 240, 285), 15: (120, 300, 480, 660, 840, 885)}
NIVELES = 3
TICK_S = 15  # todas las fotos caen en múltiplos de 15 s del reloj
UTC8 = timezone(timedelta(hours=8))
SALIDA = Path("results/okx_dentro")


def inst_id(moneda: str, inicio: datetime, dur: int) -> str:
    a = inicio.astimezone(UTC8)
    return f"{MONEDAS[moneda][0]}-UPDOWN-{dur}MIN-{a:%y%m%d}-{a:%H%M}-{a + timedelta(minutes=dur):%H%M}"


def pendientes(t: datetime) -> list[tuple[int, datetime, int]]:
    """Fotos que tocan en el instante t (múltiplo de 15 s): (duración, inicio de la ventana, segundo dentro)."""
    out = []
    for dur, segs in FOTOS.items():
        base = t.replace(second=0, microsecond=0)
        inicio = base - timedelta(minutes=base.minute % dur)
        seg = int((t - inicio).total_seconds())
        if seg in segs:
            out.append((dur, inicio, seg))
    return out


def _get(session, path: str, **params) -> dict:
    r = session.get(OKX + path, params=params, timeout=5)
    r.raise_for_status()
    return r.json()


def libro(session, inst: str) -> dict:
    j = _get(session, "/api/v5/market/books", instId=inst, sz=NIVELES)
    if str(j.get("code")) != "0":
        return {"error": f"{j.get('code')} {j.get('msg')}"[:120]}
    d = (j.get("data") or [{}])[0]
    return {k: [[float(x[0]), float(x[1])] for x in (d.get(src) or [])[:NIVELES]]
            for k, src in (("a", "asks"), ("b", "bids"))}


def indice(session, nombre: str) -> float | None:
    j = _get(session, "/api/v5/market/index-tickers", instId=nombre)
    d = (j.get("data") or [{}])[0]
    return float(d["idxPx"]) if d.get("idxPx") else None


def resultados(session, moneda: str, dur: int) -> list[dict]:
    """Resultados oficiales de los contratos vencidos más recientes de la serie (una página)."""
    j = _get(session, "/api/v5/public/event-contract/markets", seriesId=f"{MONEDAS[moneda][0]}-UPDOWN-{dur}MIN",
             state="expired")
    return [{"inst": x["instId"], "partida": float(x["floorStrike"]), "liquidacion": float(x["settleValue"]),
             "resultado": x.get("outcome"), "vence": int(x["expTime"])}
            for x in j.get("data") or [] if x.get("settleValue")]


def _iso(t: datetime) -> str:
    return t.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def grabar(horas: float, salida: Path = SALIDA, fuente: str = "local", session=None, ahora=None, dormir=time.sleep,
           log=print) -> Path:
    session = session or requests.Session()
    ahora = ahora or (lambda: datetime.now(timezone.utc))
    inicio = ahora()
    fin = inicio + timedelta(hours=horas)
    salida = Path(salida)
    salida.mkdir(parents=True, exist_ok=True)
    fotos_f = salida / f"{inicio:%Y-%m-%d_%H%M}.jsonl"
    res_f = salida / f"{inicio:%Y-%m-%d_%H%M}_resultados.jsonl"
    vistos: set[str] = set()
    n = 0
    log(f"Grabando el libro dentro de las ventanas hasta {_iso(fin)} en {fotos_f}")
    while True:
        t = ahora()
        prox = t.replace(microsecond=0) + timedelta(seconds=TICK_S - t.second % TICK_S)
        if prox > fin:
            break
        espera = (prox - ahora()).total_seconds()
        if espera > 0:
            dormir(espera)
        filas = []
        trabajos = pendientes(prox)
        idx = {}
        if trabajos:
            for m, (_, nombre) in MONEDAS.items():
                try:
                    idx[m] = indice(session, nombre)
                except (requests.RequestException, ValueError, KeyError, IndexError):
                    idx[m] = None
        for dur, ini, seg in trabajos:
            for m in MONEDAS:
                inst = inst_id(m, ini, dur)
                try:
                    foto = libro(session, inst)
                except (requests.RequestException, ValueError, KeyError, IndexError) as exc:
                    foto = {"error": f"{type(exc).__name__}"}
                filas.append({"t": _iso(ahora()), "objetivo": _iso(prox), "fuente": fuente, "dur": dur, "moneda": m,
                              "inst": inst, "seg": seg, "indice": idx.get(m), **foto})
        if filas:
            with fotos_f.open("a", encoding="utf-8") as f:
                f.write("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in filas))
            n += len(filas)
        if prox.minute % 5 == 0 and prox.second == 15:  # resultados de lo que acaba de vencer
            nuevos = []
            for m in MONEDAS:
                for dur in FOTOS:
                    try:
                        nuevos += [r for r in resultados(session, m, dur) if r["inst"] not in vistos]
                    except (requests.RequestException, ValueError, KeyError, IndexError):
                        pass
            if nuevos:
                vistos.update(r["inst"] for r in nuevos)
                with res_f.open("a", encoding="utf-8") as f:
                    f.write("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in nuevos))
    log(f"{n} fotos dentro de las ventanas en {fotos_f}")
    return fotos_f


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Graba el libro de OKX dentro de cada ventana (5 y 15 min).")
    p.add_argument("--horas", type=float, default=5.7)
    p.add_argument("--salida", default=str(SALIDA))
    p.add_argument("--fuente", default="local")
    a = p.parse_args(argv)
    grabar(a.horas, Path(a.salida), a.fuente)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
