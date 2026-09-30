"""Cuenta simulada (papel): registra operaciones hipotéticas y sus resultados. Sin dinero real."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from ..signals.alert import Alert
from ..timeutil import utcnow


@dataclass
class PaperLedger:
    path: Path
    stake: float = 1.0
    balance: float = 0.0
    trades: list = field(default_factory=list)

    def record(self, alert: Alert, pnl_units: float, tie: bool, win: bool, shadow: bool) -> dict:
        """`shadow=True` marca operaciones de alertas EXPERIMENTALES (hipotéticas, fuera del saldo)."""
        pnl = pnl_units * self.stake
        if not shadow:
            self.balance += pnl
        row = {"time": utcnow().isoformat(), "alert_id": alert.alert_id, "instrument": alert.instrument,
               "direction": alert.direction, "status": alert.status, "prob": alert.prob, "pnl": pnl,
               "win": win, "tie": tie, "shadow": shadow, "balance": self.balance}
        self.trades.append(row)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        return row
