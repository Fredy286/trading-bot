"""Cuenta simulada (papel): registra operaciones hipotéticas y sus resultados. Sin dinero real."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .. import jsonutil
from ..signals.alert import Alert
from ..timeutil import utcnow


def read_rows(path: Path) -> tuple[list[dict], int]:
    """Filas válidas de un .jsonl y cuántas líneas dañadas se descartaron (p. ej. tras un apagón)."""
    rows, bad = [], 0
    for r in jsonutil.iter_jsonl(path):
        if isinstance(r, dict):
            rows.append(r)
        else:
            bad += 1
    return rows, bad


@dataclass
class PaperLedger:
    path: Path
    stake: float = 1.0
    balance: float = 0.0
    trades: list = field(default_factory=list)

    def reload(self, model_id: str | None) -> int:
        """Recupera las filas de `model_id` ya registradas (reinicio de `tbot live`). Devuelve líneas dañadas."""
        rows, bad = read_rows(self.path)
        self.trades = [r for r in rows if r.get("model_id") == model_id]
        self.balance = sum(r["pnl"] for r in self.trades if not r.get("shadow"))
        return bad

    def record(self, alert: Alert, pnl_units: float, tie: bool, win: bool, shadow: bool,
               method: str | None = None, extra: dict | None = None) -> dict:
        """`shadow=True` marca operaciones hipotéticas (EXPERIMENTAL o PAUSADO), fuera del saldo."""
        pnl = pnl_units * self.stake
        if not shadow:
            self.balance += pnl
        row = {"time": utcnow().isoformat(), "alert_id": alert.alert_id, "instrument": alert.instrument,
               "model_id": alert.model_id, "duration_min": alert.duration_min, "contract": alert.contract,
               "payout": alert.payout, "tie_rule": (alert.costs or {}).get("regla_empate"),
               "breakeven": alert.breakeven, "method": method, "ic_filter_ok": alert.ic_filter_ok,
               "direction": alert.direction, "status": alert.status, "prob": alert.prob, "pnl": pnl,
               "win": win, "tie": tie, "shadow": shadow, "balance": self.balance, **(extra or {})}
        self.trades.append(row)
        jsonutil.append_line(self.path, json.dumps(row, ensure_ascii=False))
        return row
