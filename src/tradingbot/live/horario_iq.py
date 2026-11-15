"""Horario del blitz de BTC con precio real en IQ Option (enmienda a los Estudios 44, 46 y 68, docs/01, 2026-11-15).

El fin de semana IQ Option solo ofrece versiones OTC (precio propio de la plataforma), que nunca se estudian ni se
recomiendan. Una vela de decisión t está «en horario abierto» si el contrato entero cae dentro del horario: la compra
al cierre de t (t + 1 min) y el vencimiento 3 min después (t + 4 min).

El horario vive en `config/horario_iq_blitz.json`, en UTC (Bogotá = UTC−5 todo el año). Mientras el usuario no lo
confirme en la plataforma, vale el horario prudente: lunes 03:00 UTC (domingo 22:00 de Bogotá) → viernes 22:00 UTC
(17:00 de Bogotá), sin pausas.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

CONFIG = Path("config/horario_iq_blitz.json")
PRUDENTE = {"zona": "UTC", "abre": {"dia": 0, "hora": "03:00"}, "cierra": {"dia": 4, "hora": "22:00"},
            "pausas": [], "confirmado_por_usuario": False}
COMPRA = pd.Timedelta(minutes=1)    # la compra es al cierre de la vela de decisión
VENCE = pd.Timedelta(minutes=4)     # el blitz dura 3 min desde la compra
MOTIVO = "IQ cerrado: no operar OTC (el blitz de Bitcoin con precio real abre el domingo 22:00 de Bogotá)"


def cargar(path: Path = CONFIG) -> dict:
    """Horario congelado; si el archivo no existe, el prudente."""
    path = Path(path)
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else dict(PRUDENTE)


def _min(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def _minutos_semana(t: pd.DatetimeIndex) -> np.ndarray:
    """Minutos desde el lunes 00:00 UTC (con fracción de segundos)."""
    t = pd.DatetimeIndex(t).tz_convert("UTC")
    return (t.dayofweek * 1440 + t.hour * 60 + t.minute + t.second / 60).to_numpy(float)


def abierto_vec(velas, horario: dict | None = None) -> np.ndarray:
    """Para cada vela de decisión, True si el contrato entero (compra → vencimiento) cae en el horario."""
    h = horario or PRUDENTE
    if h.get("zona", "UTC") != "UTC":
        raise ValueError("El horario de IQ se guarda en UTC (Bogotá = UTC−5).")
    velas = pd.DatetimeIndex(velas)
    a = _minutos_semana(velas + COMPRA)
    b = a + (VENCE - COMPRA) / pd.Timedelta(minutes=1)
    abre = h["abre"]["dia"] * 1440 + _min(h["abre"]["hora"])
    cierra = h["cierra"]["dia"] * 1440 + _min(h["cierra"]["hora"])
    ok = (a >= abre) & (b <= cierra)
    for p in h.get("pausas", []):  # pausas diarias en UTC [desde, hasta)
        d0, d1 = _min(p["desde"]), _min(p["hasta"])
        for dia in range(7):
            p0, p1 = dia * 1440 + d0, dia * 1440 + d1
            ok &= ~((a < p1) & (b > p0))
    return ok


def abierto(vela, horario: dict | None = None) -> bool:
    return bool(abierto_vec(pd.DatetimeIndex([pd.Timestamp(vela)]), horario)[0])
