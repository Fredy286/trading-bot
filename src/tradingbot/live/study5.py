"""Estudio 5 (pre-registro en docs/01, commit 53344b4): confirmación del modelo registrado de BTC 1 min con
datos nuevos y entrada manual realista (+10 s).

Se evalúa el libro de una reproducción (`tbot replay --entry-delay-s 10`) que empieza el 2026-10-04:
- H5a: primeras 3 500 alertas sin empate, a cualquier hora;
- H5b: primeras 2 500 alertas sin empate de sábado y domingo (UTC), del mismo libro.
Enmienda del 2026-10-24 (antes de reproducir datos nuevos): Bonferroni en lugar de Holm, cada hipótesis con
p unilateral < 0,025 frente a p*, evaluada por separado en cuanto su muestra está completa (o vence el plazo).
Cada una aprueba si además el límite inferior de Wilson 95 % > p* y el EV > 0. Si la muestra no se completa
al 2026-12-13, «no concluyente».

Mientras la muestra de una hipótesis esté incompleta y no haya vencido el plazo, solo se informa su conteo.
"""

from __future__ import annotations

import pandas as pd

from ..research.metrics import binom_pvalue_greater, wilson
from ..signals.monitor import fixed_sample
from .runner import LIVE_METHOD

START = pd.Timestamp("2026-10-04", tz="UTC")
# «Si al 2026-12-13 no se completa»: cuentan las alertas de todo ese día (UTC), es decir, hasta el 14 excluido.
DEADLINE_END = pd.Timestamp("2026-12-14", tz="UTC")
ENTRY_DELAY_S = 10.0
SAMPLE_N = {"H5a": 3500, "H5b": 2500}
ALPHA = 0.025  # por hipótesis (Bonferroni, 2 hipótesis): error de familia ≤ 5 %


def is_weekend(row: dict) -> bool:
    """Sábado o domingo en UTC, según la vela de decisión (la hora en que se emite la alerta)."""
    return pd.Timestamp(row["decision_time"]).tz_convert("UTC").dayofweek >= 5


def eligible_rows(rows: list[dict], obs: dict) -> tuple[list[dict], dict]:
    """Alertas del modelo y la política registrados, desde el 2026-10-04 y dentro del plazo, una por vela."""
    excl = {"de_otro_modelo_o_metodo": 0, "politica_distinta": 0, "fuera_del_periodo": 0,
            "vela_de_decision_repetida": 0}
    sel = []
    for r in sorted(rows, key=lambda r: str(r.get("time", ""))):
        if r.get("model_id") != obs["model_id"] or r.get("method") != LIVE_METHOD:
            excl["de_otro_modelo_o_metodo"] += 1
        elif r.get("policy") != obs["policy"]:
            excl["politica_distinta"] += 1
        elif not START <= pd.Timestamp(r["decision_time"]) < DEADLINE_END:
            excl["fuera_del_periodo"] += 1
        else:
            sel.append(r)
    seen, out = set(), []
    for r in sel:
        if r["decision_time"] in seen:
            excl["vela_de_decision_repetida"] += 1
            continue
        seen.add(r["decision_time"])
        out.append(r)
    return out, excl


def _stats(sample: list[dict], breakeven: float) -> dict:
    nt = [r for r in sample if not r.get("tie")]
    n, wins = len(nt), sum(1 for r in nt if r.get("win"))
    lo, hi = wilson(wins, n) if n else (float("nan"), float("nan"))
    return {"n": n, "aciertos": wins, "empates": len(sample) - n, "acierto": wins / n if n else None,
            "lo95": float(lo), "hi95": float(hi),
            "ev": sum(r["pnl"] for r in sample) / len(sample) if sample else None,
            "p": binom_pvalue_greater(wins, n, breakeven) if n else 1.0}


def _by(sample: list[dict], key) -> dict:
    out: dict = {}
    for r in sample:
        if r.get("tie"):
            continue
        g = out.setdefault(key(r), {"n": 0, "aciertos": 0})
        g["n"] += 1
        g["aciertos"] += 1 if r.get("win") else 0
    return dict(sorted(out.items()))


def evaluate(rows: list[dict], obs: dict, data_end: pd.Timestamp, sensitivity=None) -> dict:
    """Veredicto del Estudio 5. `data_end` = fin (excluido) de los datos reproducidos.

    `sensitivity(sample)` (opcional) devuelve la sensibilidad informativa de una muestra: entrada a otros
    segundos y pago del 80 %. Solo se llama para las hipótesis evaluadas.
    """
    elig, excl = eligible_rows(rows, obs)
    bad = [r.get("entrada_tras_cierre_s") for r in elig
           if r.get("entrada_tras_cierre_s") is None or abs(r["entrada_tras_cierre_s"] - ENTRY_DELAY_S) > 0.5]
    if bad:
        raise ValueError(f"El libro no es de una reproducción con entrada a +{ENTRY_DELAY_S:g} s "
                         f"({len(bad)} alertas con otra entrada, p. ej. {bad[0]}).")
    pools = {"H5a": elig, "H5b": [r for r in elig if is_weekend(r)]}
    samples = {h: fixed_sample(pools[h], SAMPLE_N[h]) for h in SAMPLE_N}
    counts = {h: sum(1 for r in samples[h] if not r.get("tie")) for h in SAMPLE_N}
    complete = {h: counts[h] >= SAMPLE_N[h] for h in SAMPLE_N}
    base = {"estudio": "Estudio 5 (pre-registro 53344b4, enmienda Bonferroni 2026-10-24)",
            "model_id": obs["model_id"], "policy": obs["policy"], "entrada_s": ENTRY_DELAY_S,
            "inicio": START.isoformat(), "plazo_fin_excluido": DEADLINE_END.isoformat(),
            "datos_hasta_excluido": pd.Timestamp(data_end).isoformat(), "objetivo": SAMPLE_N, "alfa": ALPHA,
            "sin_empate_en_muestra": counts, "completa": complete, "excluidas": excl}
    expired = pd.Timestamp(data_end) >= DEADLINE_END
    be = 1 / (1 + obs["policy"]["payout"])
    hyps = {}
    for h in SAMPLE_N:
        if not complete[h] and not expired:
            hyps[h] = {"estado": "pendiente", "sin_empate": counts[h], "objetivo": SAMPLE_N[h]}
            continue
        s = _stats(samples[h], be)
        if not complete[h]:
            estado = "no concluyente"
        else:
            estado = "aprueba" if s["p"] < ALPHA and s["lo95"] > be and (s["ev"] or 0) > 0 else "no aprueba"
        hyps[h] = {**s, "umbral": be, "estado": estado,
                   "por_dia_utc": _by(samples[h], lambda r: pd.Timestamp(r["decision_time"]).strftime("%Y-%m-%d")),
                   "por_dia_semana_utc": _by(samples[h], lambda r: pd.Timestamp(r["decision_time"]).dayofweek),
                   "sensibilidad": sensitivity(samples[h]) if sensitivity else None}
    st = {h: hyps[h]["estado"] for h in hyps}
    if st["H5a"] == "aprueba":
        conclusion = "Aprueba H5a: señales manuales experimentales en cuenta DEMO, a cualquier hora."
    elif st["H5b"] == "aprueba":
        conclusion = "Solo aprueba H5b: señales manuales experimentales en cuenta DEMO, solo sábados y domingos."
    elif "pendiente" in st.values():
        conclusion = "Sin decisión todavía: " + ", ".join(f"{h} {e}" for h, e in st.items()) + "."
    else:
        conclusion = "No aprueba ninguna: BTC a 1 minuto queda SIN SEÑAL también para uso manual."
    n_pend = sum(e == "pendiente" for e in st.values())
    estado = "pendiente" if n_pend == len(st) else ("parcial" if n_pend else "final")
    return {**base, "estado": estado, "hipotesis": hyps, "conclusion": conclusion,
            "nota": "Nunca dinero real sin autorización expresa; antes, prueba en demo del precio, el empate y el pago."}
