"""Simulación de condiciones reales de ejecución para una lista de señales.

Cada señal pasa por: latencia (alerta + orden, lognormal) → caducidad (latencia > vigencia máxima)
→ desconexión (probabilidad fija) → precio efectivo de entrada (con velas M1: la latencia ≥ 60 s
retrasa la entrada una vela) → resultado neto según el contrato.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .contracts import BinaryContract, SpotContract

STATUS = {
    0: "ejecutada",
    1: "sin_señal",
    2: "filtrada_noticias",
    3: "caducada",
    4: "desconexión",
    5: "no_evaluable",
}


@dataclass(frozen=True)
class ExecParams:
    latency_median_s: float = 3.0
    latency_sigma: float = 0.5
    max_age_s: float = 20.0
    p_disconnect: float = 0.01
    seed: int = 2024


def max_age_for_horizon(h_min: int, base_s: float = 20.0) -> float:
    """Vigencia máxima de una señal: 20 s o un tercio del horizonte, lo que sea mayor."""
    return max(base_s, h_min * 60 / 3)


def simulate(side: np.ndarray, want: np.ndarray, news_block: np.ndarray, labels_by_delay: dict,
             contract, params: ExecParams, extra: dict | None = None) -> dict:
    """Devuelve estado y PnL por señal.

    side:  +1/−1/0 dirección propuesta.   want: la política quiere operar.
    news_block: la política excluye por ventana de noticias.
    labels_by_delay: {1: DataFrame etiquetas d=1, 2: DataFrame d=2} alineados con side.
    """
    n = len(side)
    rng = np.random.default_rng(params.seed)
    lat = rng.lognormal(np.log(max(params.latency_median_s, 1e-3)), params.latency_sigma, n)
    disc = rng.random(n) < params.p_disconnect
    delay = 1 + (lat // 60).astype(int)

    status = np.full(n, 1, dtype=np.int8)
    active = want & (side != 0)
    status[active & news_block] = 2
    go = active & ~news_block
    status[go & (lat > params.max_age_s)] = 3
    go &= lat <= params.max_age_s
    status[go & disc] = 4
    go &= ~disc
    go &= delay <= max(labels_by_delay)  # entradas más tardías que las etiquetas calculadas: caducan
    status[active & ~news_block & (lat <= params.max_age_s) & ~disc & (delay > max(labels_by_delay))] = 3

    realized = np.full(n, np.nan)
    long_px = np.full(n, np.nan)
    short_px = np.full(n, np.nan)
    entry = np.full(n, np.nan)
    spread_in = np.full(n, np.nan)
    for d, lab in labels_by_delay.items():
        m = go & (delay == d)
        realized[m] = lab["dir"].to_numpy()[m]
        long_px[m] = lab["long_px"].to_numpy()[m]
        short_px[m] = lab["short_px"].to_numpy()[m]
        entry[m] = lab["entry"].to_numpy()[m]
        spread_in[m] = lab["spread_in"].to_numpy()[m]
    unevaluable = go & np.isnan(realized)
    status[unevaluable] = 5
    ex = go & ~unevaluable
    status[ex] = 0

    pnl = np.full(n, np.nan)
    if isinstance(contract, BinaryContract):
        pnl[ex] = contract.pnl(side[ex], realized[ex])
    elif isinstance(contract, SpotContract):
        pnl[ex] = contract.pnl_bps(side[ex], long_px[ex], short_px[ex], entry[ex])
    else:  # pragma: no cover
        raise TypeError("Contrato desconocido")
    return {"status": status, "pnl": pnl, "realized": realized, "latency_s": lat, "executed": ex}
