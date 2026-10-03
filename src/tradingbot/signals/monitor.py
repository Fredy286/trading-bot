"""Monitor de deterioro en observación en vivo (sin dinero real).

Reglas pre-registradas (protocolo, sección 8):
- Con ≥ `min_n` señales evaluadas (sin empates), si el límite SUPERIOR de Wilson 95 % del acierto
  acumulado o de la ventana móvil queda por debajo del umbral de rentabilidad → PAUSADO.
- Si la probabilidad media anunciada supera la frecuencia observada de forma significativa
  (z < −2,5) → EXPERIMENTAL (probabilidades sobreestimadas).
Las reglas NO se ajustan retrospectivamente para convertir un mal periodo en éxito.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..research.metrics import wilson


@dataclass
class MonitorResult:
    status: str  # OK | EXPERIMENTAL | PAUSADO | SIN_DATOS
    n: int
    hit: float | None
    hit_hi95: float | None
    mean_prob: float | None
    calib_z: float | None
    detail: str

    def to_dict(self) -> dict:
        return dict(self.__dict__)


def evaluate_monitor(outcomes: list[dict], breakeven: float, min_n: int = 50, window: int = 200) -> MonitorResult:
    """`outcomes`: dicts con claves `win` (bool), `tie` (bool) y `prob` (probabilidad anunciada)."""
    rows = [o for o in outcomes if not o.get("tie")]
    n = len(rows)
    if n == 0:
        return MonitorResult("SIN_DATOS", 0, None, None, None, None, "Aún no hay señales evaluadas.")
    wins = np.array([bool(o["win"]) for o in rows])
    probs = np.array([o.get("prob") if o.get("prob") is not None else np.nan for o in rows], float)
    hit = float(wins.mean())
    _, hi = wilson(wins.sum(), n)
    mean_p = float(np.nanmean(probs)) if np.isfinite(probs).any() else None
    z = None
    if mean_p is not None and 0 < mean_p < 1:
        z = float((hit - mean_p) / np.sqrt(mean_p * (1 - mean_p) / n))
    if n < min_n:
        return MonitorResult("OK", n, hit, hi, mean_p, z,
                             f"Observación en curso: {n}/{min_n} señales para poder juzgar.")
    w = wins[-window:]
    _, hi_w = wilson(w.sum(), len(w))
    if hi < breakeven or hi_w < breakeven:
        return MonitorResult("PAUSADO", n, hit, hi, mean_p, z,
                             f"Acierto {hit:.1%} con límite superior {min(hi, hi_w):.1%} < umbral {breakeven:.1%}: "
                             "alertas pausadas.")
    if z is not None and z < -2.5:
        return MonitorResult("EXPERIMENTAL", n, hit, hi, mean_p, z,
                             f"Probabilidades sobreestimadas (anunciada {mean_p:.1%} vs observada {hit:.1%}).")
    return MonitorResult("OK", n, hit, hi, mean_p, z, "Sin deterioro detectado.")


# Aclaración 2 (corregida antes de iniciar la observación): se juzga una sola vez, con las primeras 3 500
# alertas sin empate. Potencia ~80 % si la ventaja real fuera la del periodo bloqueado (56,4 %); con 200
# era ~11 %. Falsos positivos ~2,3 % en ambos casos.
LIVE_SAMPLE_N = 3500
LIVE_MAX_DAYS = 56  # si la muestra no se completa en 8 semanas, el resultado es «no concluyente»


def fixed_sample(rows: list[dict], n: int = LIVE_SAMPLE_N) -> list[dict]:
    """Primeras filas, en orden de tiempo, hasta completar `n` alertas sin empate (empates intermedios incluidos).

    Con una muestra fija, consultar el veredicto a diario no cambia el resultado: no hay «parar en el primer
    aprobado».
    """
    out, nontie = [], 0
    for r in sorted(rows, key=lambda r: str(r.get("time", ""))):
        if nontie >= n:
            break
        out.append(r)
        nontie += 0 if r.get("tie") else 1
    return out


def live_verdict(ledger_rows: list[dict], breakeven: float, symbol: str, model: str,
                 min_n: int = LIVE_SAMPLE_N) -> dict:
    """Veredicto de la observación en vivo SIN dinero (criterios fijos, no ajustables a posteriori):
    ≥ `min_n` alertas evaluadas sin empate, límite inferior de Wilson 95 % del acierto > umbral y
    EV medio > 0. Se evalúan TODAS las alertas del periodo, incluidas las malas.
    """
    rows = [r for r in ledger_rows if not r.get("tie")]
    n = len(rows)
    wins = sum(1 for r in rows if r.get("win"))
    lo, hi = wilson(wins, n) if n else (float("nan"), float("nan"))
    ev = float(np.mean([r["pnl"] for r in ledger_rows])) if ledger_rows else float("nan")
    passed = bool(n >= min_n and lo > breakeven and ev > 0)
    reasons = []
    if n < min_n:
        reasons.append(f"muestra insuficiente: {n} < {min_n}")
    if n and not lo > breakeven:
        reasons.append(f"límite inferior {lo:.1%} ≤ umbral {breakeven:.1%}")
    if not ev > 0:
        reasons.append(f"EV medio {ev:+.4f} ≤ 0")
    return {"symbol": symbol, "model": model, "n": n, "wins": wins, "hit": wins / n if n else None,
            "hit_lo95": lo, "hit_hi95": hi, "ev": ev, "breakeven": breakeven, "min_n": min_n,
            "passed": passed, "reasons": reasons}
