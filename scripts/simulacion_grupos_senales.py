"""Cómo se fabrica un «90 % de acierto» con señales AL AZAR (docs/05, sección 3).

Usa velas reales de 1 minuto de BTC/USDT (Binance, 2025-09-01 → 2026-08-31, ya usadas en la Fase 1B: aquí
no se selecciona ni se entrena nada, así que no hay riesgo de sesgo) y simula señales de 1 minuto con
dirección aleatoria, contadas como las cuentan los grupos de señales:

1. Reintentos («gale», «M1/M2/M3»): si la operación pierde, se repite en el minuto siguiente con más
   dinero, y el ciclo cuenta como «acierto» si gana en cualquier intento.
2. Muchos canales: de 1 000 canales que publican señales al azar, se muestra el mejor del mes.

Contrato: pago 85 %, empate reembolsado (el mismo intento se repite en el minuto siguiente).

Uso: .venv/bin/python scripts/simulacion_grupos_senales.py  → results/grupos_senales.json
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
PAGO = 0.85
SEMILLA = 20261024


def cargar_resultados_1min() -> np.ndarray:
    """+1 si la vela de 1 min cierra arriba, −1 abajo, 0 empate (precio de las velas de Binance)."""
    partes = [pd.read_parquet(RAIZ / f"data/raw/binance/BTCUSDT/{a}.parquet") for a in (2025, 2026)]
    d = pd.concat(partes).sort_index()
    d = d.loc["2025-09-01":"2026-08-31"]
    return np.sign(d["bid_c"].to_numpy() - d["bid_o"].to_numpy()).astype(int)


def ciclo(mov: np.ndarray, inicio: int, direccion: int, apuestas: list[float]) -> tuple[int, float, float]:
    """Juega un ciclo con reintentos. Devuelve (intento ganador o 0, ganancia neta, total apostado)."""
    t, neto, apostado = inicio, 0.0, 0.0
    for k, a in enumerate(apuestas, start=1):
        while t < len(mov) and mov[t] == 0:  # empate: se reembolsa y se repite el mismo intento
            t += 1
        if t >= len(mov):
            break
        apostado += a
        if mov[t] == direccion:
            return k, neto + a * PAGO, apostado
        neto -= a
        t += 1
    return 0, neto, apostado


def simular(mov: np.ndarray, rng: np.random.Generator, n: int, apuestas: list[float]) -> dict:
    inicios = rng.integers(0, len(mov) - 50, size=n)
    direcciones = rng.choice([-1, 1], size=n)
    res = [ciclo(mov, int(i), int(d), apuestas) for i, d in zip(inicios, direcciones)]
    gan = np.array([r[0] for r in res])
    neto = np.array([r[1] for r in res])
    apostado = np.array([r[2] for r in res])
    return {
        "apuestas": apuestas,
        "ciclos": n,
        "acierto_por_ciclo": float((gan > 0).mean()),
        "gana_en_intento": {str(k): float((gan == k).mean()) for k in range(1, len(apuestas) + 1)},
        "pierde_todo": float((gan == 0).mean()),
        "perdida_si_pierde_todo": -float(sum(apuestas)),
        "ganancia_media_por_ciclo": float(neto.mean()),
        "ev_por_unidad_apostada": float(neto.sum() / apostado.sum()),
    }


def canales(mov: np.ndarray, rng: np.random.Generator, n_canales: int, senales_mes: int,
            apuestas: list[float]) -> dict:
    """n_canales publican señales al azar dos meses seguidos; se elige el mejor del primer mes."""
    def mes() -> tuple[np.ndarray, np.ndarray]:
        acierto, neto = np.empty(n_canales), np.empty(n_canales)
        for c in range(n_canales):
            inicios = rng.integers(0, len(mov) - 50, size=senales_mes)
            dirs = rng.choice([-1, 1], size=senales_mes)
            r = [ciclo(mov, int(i), int(d), apuestas) for i, d in zip(inicios, dirs)]
            acierto[c] = np.mean([x[0] > 0 for x in r])
            neto[c] = sum(x[1] for x in r)
        return acierto, neto

    a1, n1 = mes()
    a2, n2 = mes()
    mejor = int(np.argmax(a1))
    return {
        "canales": n_canales,
        "senales_por_mes": senales_mes,
        "apuestas": apuestas,
        "acierto_mes1": {
            "mediana": float(np.median(a1)),
            "p95": float(np.quantile(a1, 0.95)),
            "maximo": float(a1.max()),
            "canales_con_90_o_mas": int((a1 >= 0.90).sum()),
        },
        "canales_con_ganancia_mes1": int((n1 > 0).sum()),
        "mejor_canal_mes1": {"acierto": float(a1[mejor]), "neto": float(n1[mejor])},
        "mismo_canal_mes2": {"acierto": float(a2[mejor]), "neto": float(n2[mejor])},
        "neto_medio_por_canal_mes1": float(n1.mean()),
    }


def main() -> None:
    mov = cargar_resultados_1min()
    rng = np.random.default_rng(SEMILLA)
    salida = {
        "datos": "BTC/USDT 1 min, Binance, 2025-09-01 a 2026-08-31",
        "minutos": int(len(mov)),
        "empates": float((mov == 0).mean()),
        "contrato": {"pago": PAGO, "empate": "reembolsado"},
        "semilla": SEMILLA,
        "reintentos": {
            "sin_reintento": simular(mov, rng, 200_000, [1]),
            "1_reintento_x2": simular(mov, rng, 200_000, [1, 2]),
            "2_reintentos_x2": simular(mov, rng, 200_000, [1, 2, 4]),
            "3_reintentos_x2": simular(mov, rng, 200_000, [1, 2, 4, 8]),
            "2_reintentos_x2.18": simular(mov, rng, 200_000, [1, 2.18, 4.75]),
        },
        "mil_canales_sin_reintento": canales(mov, rng, 1000, 300, [1]),
        "mil_canales_2_reintentos": canales(mov, rng, 1000, 300, [1, 2, 4]),
    }
    destino = RAIZ / "results/grupos_senales.json"
    destino.write_text(json.dumps(salida, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(salida, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
