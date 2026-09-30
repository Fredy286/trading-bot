"""Contratos y costos: opción de pago fijo («binaria») y contado/CFD.

Unidades:
- Binaria: resultados en unidades de apuesta (ganar = +payout, perder = −1, empate = 0 o −1).
- Contado: resultados en puntos básicos (pb) del precio de entrada, netos de spread y comisión.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class BinaryContract:
    payout: float = 0.85
    tie_rule: str = "refund"  # "refund" | "loss"
    name: str = "binaria"

    @property
    def tie_value(self) -> float:
        return 0.0 if self.tie_rule == "refund" else -1.0

    def breakeven(self, tie_prob: float = 0.0) -> float:
        """Acierto mínimo (entre operaciones sin empate) para EV = 0."""
        if self.tie_rule == "refund":
            return 1.0 / (1.0 + self.payout)
        return 1.0 / ((1.0 - tie_prob) * (1.0 + self.payout))

    def pnl(self, side: np.ndarray, realized_dir: np.ndarray) -> np.ndarray:
        side = np.asarray(side, float)
        d = np.asarray(realized_dir, float)
        win = side == d
        return np.where(d == 0, self.tie_value, np.where(win, self.payout, -1.0))

    def ev(self, p_dir: np.ndarray, tie_prob: np.ndarray) -> np.ndarray:
        p = np.asarray(p_dir, float)
        q = np.asarray(tie_prob, float)
        return (1 - q) * (p * self.payout - (1 - p)) + q * self.tie_value


@dataclass(frozen=True)
class SpotContract:
    commission_px: float = 0.0  # ida y vuelta, en unidades de precio
    commission_bps: float = 0.0  # ida y vuelta, en pb
    slippage_px: float = 0.0  # adicional, ida y vuelta
    name: str = "contado"

    def cost_bps(self, entry: np.ndarray, spread_px: np.ndarray) -> np.ndarray:
        entry = np.asarray(entry, float)
        return (np.asarray(spread_px, float) + self.commission_px + self.slippage_px) / entry * 1e4 + self.commission_bps

    def pnl_bps(self, side: np.ndarray, long_px: np.ndarray, short_px: np.ndarray, entry: np.ndarray) -> np.ndarray:
        """PnL neto en pb. long_px/short_px ya descuentan el spread observado."""
        side = np.asarray(side, float)
        gross = np.where(side > 0, long_px, short_px)
        extra = (self.commission_px + self.slippage_px) / np.asarray(entry, float) * 1e4 + self.commission_bps
        return np.asarray(gross, float) / np.asarray(entry, float) * 1e4 - extra

    def ev_bps(self, p_dir: np.ndarray, abs_move_bps: np.ndarray, cost_bps: np.ndarray) -> np.ndarray:
        """EV ≈ (2p − 1)·m − c (aproximación simétrica: ganancia y pérdida medias iguales a m)."""
        return (2 * np.asarray(p_dir, float) - 1) * np.asarray(abs_move_bps, float) - np.asarray(cost_bps, float)

    @staticmethod
    def breakeven(abs_move_bps: float, cost_bps: float) -> float:
        """Acierto mínimo aproximado p* = 0,5 + c/(2m). Si c ≥ m es inalcanzable (> 1)."""
        if abs_move_bps <= 0:
            return float("inf")
        return 0.5 + cost_bps / (2 * abs_move_bps)
