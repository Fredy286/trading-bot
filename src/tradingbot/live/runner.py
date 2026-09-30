"""Bucle de alertas: genera, notifica, registra tiempos y evalúa cada alerta al vencer.

Registro de eventos (runtime/<dir>/events.jsonl), una línea por evento:
  generated  → alerta creada (incluye la hora de recepción de los datos usados)
  sent       → notificada por un canal
  received   → confirmada por el usuario en el panel (POST /api/ack)
  evaluated  → resultado conocido tras el vencimiento
`state.json` es una instantánea para el panel web.
"""

from __future__ import annotations

import json
import time
from collections import deque
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from ..config import Settings, load_dotenv
from ..execution.paper import PaperLedger
from ..instruments import get_instrument
from ..research.contracts import BinaryContract
from ..signals.alert import EXPERIMENTAL, NO_SIGNAL, SIGNAL, Alert
from ..signals.engine import RiskState, SignalEngine
from ..signals.monitor import evaluate_monitor
from ..timeutil import utcnow


class EventLog:
    def __init__(self, runtime_dir: Path):
        self.dir = Path(runtime_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.path = self.dir / "events.jsonl"

    def write(self, event: str, alert: Alert, **extra) -> None:
        row = {"event": event, "time": utcnow().isoformat(), "alert_id": alert.alert_id, **extra}
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")


class AlertLoop:
    def __init__(self, engine: SignalEngine, feed, notifiers: list, runtime_dir: Path, settings: Settings,
                 clock=utcnow):
        self.engine, self.feed, self.notifiers = engine, feed, notifiers
        self.s, self.clock = settings, clock
        self.dir = Path(runtime_dir)
        self.log = EventLog(self.dir)
        self.risk = RiskState()
        self.ledger = PaperLedger(self.dir / "paper_ledger.jsonl", settings.stake)
        self.alerts: deque[Alert] = deque(maxlen=300)
        self.pending: list[Alert] = []
        self.outcomes: list[dict] = []
        self.monitor = evaluate_monitor([], 0.5)
        self.last_data_time = None
        self.last_status = None
        self.status_counts: dict[str, int] = {}

    # ------------------------------------------------------------------ ciclo
    def step(self, now_utc: datetime | None = None) -> Alert:
        now = now_utc or self.clock()
        bars, received_at = self.feed.get(now)
        if len(bars):
            self.last_data_time = bars.index[-1] + pd.Timedelta(minutes=1)
        alert = self.engine.evaluate(bars, now, self.risk, self.monitor.status)
        alert.generated_at = now
        self.log.write("generated", alert, data_received_at=received_at, status=alert.status,
                       payload=alert.to_dict())
        if alert.status in (SIGNAL, EXPERIMENTAL):
            for n in self.notifiers:
                try:
                    t = n.send(alert)
                    alert.sent_at = alert.sent_at or t
                    self.log.write("sent", alert, channel=n.name, sent_at=t)
                except Exception as exc:  # un canal caído no detiene el sistema
                    self.log.write("send_failed", alert, channel=n.name, error=str(exc))
            self.pending.append(alert)
        elif alert.status != self.last_status:
            # «SIN SEÑAL» se registra; en consola solo se imprime cuando cambia el estado.
            for n in self.notifiers:
                if n.name == "console":
                    print(f"{alert.one_line()} — {alert.no_signal_reason}", flush=True)
        self.last_status = alert.status
        self.status_counts[alert.status] = self.status_counts.get(alert.status, 0) + 1
        self.alerts.appendleft(alert)
        self._evaluate_pending(bars, now)
        self.write_state()
        return alert

    def _evaluate_pending(self, bars: pd.DataFrame, now: datetime) -> None:
        still = []
        for a in self.pending:
            entry_t = pd.Timestamp(a.decision_time)  # vela que abre en el momento de decisión
            exit_t = entry_t + pd.Timedelta(minutes=a.duration_min - 1)
            if exit_t not in bars.index or entry_t not in bars.index:
                if pd.Timestamp(now) - exit_t > pd.Timedelta(minutes=30):
                    a.outcome = {"resultado": "no_evaluable", "motivo": "faltan velas"}
                    a.evaluated_at = now
                    self.log.write("evaluated", a, outcome=a.outcome)
                else:
                    still.append(a)
                continue
            o, c = bars.at[entry_t, "o"], bars.at[exit_t, "c"]
            if np.isnan(o) or np.isnan(c):
                a.outcome = {"resultado": "no_evaluable", "motivo": "vela vacía"}
            else:
                d = np.sign(round((c - o) / (self.engine.inst.point / 2)))
                side = 1 if a.direction == "sube" else -1
                tie, win = d == 0, d == side
                if isinstance(self.engine.contract, BinaryContract):
                    pnl = float(self.engine.contract.pnl(np.array([side]), np.array([d]))[0])
                else:
                    sp = bars.at[entry_t, "spread_o"] / 2 + bars.at[exit_t, "spread_c"] / 2
                    pnl = float(side * (c - o) - sp) / o * 1e4
                a.outcome = {"resultado": "empate" if tie else ("acierto" if win else "fallo"),
                             "entrada": float(o), "salida": float(c), "pnl": pnl}
                shadow = a.status != SIGNAL
                self.ledger.record(a, pnl, bool(tie), bool(win), shadow)
                if not shadow:
                    self.risk.register_outcome(pnl)
                self.outcomes.append({"win": bool(win), "tie": bool(tie), "prob": a.prob})
                be = a.breakeven if a.breakeven and a.breakeven <= 1 else 0.5
                self.monitor = evaluate_monitor(self.outcomes, be)
            a.evaluated_at = now
            self.log.write("evaluated", a, outcome=a.outcome, evaluated_at=now)
        self.pending = still

    # ------------------------------------------------------------------ estado para el panel
    def write_state(self) -> None:
        counts = dict(self.status_counts)
        b = self.engine.b
        state = {
            "updated_at": utcnow().isoformat(),
            "settings": self.s.public_dict(),
            "model": {"model_id": b.model_id, "validation_status": b.validation_status,
                      "validation_evidence": b.validation_evidence, "synthetic": b.synthetic,
                      "trained_from": b.trained_from, "trained_to": b.trained_to},
            "monitor": self.monitor.to_dict(),
            "last_data_time": self.last_data_time.isoformat() if self.last_data_time is not None else None,
            "counts": counts,
            "paper": {"balance": self.ledger.balance, "n": len(self.ledger.trades),
                      "shadow_n": sum(1 for t in self.ledger.trades if t["shadow"]),
                      "shadow_pnl": sum(t["pnl"] for t in self.ledger.trades if t["shadow"])},
            "alerts": [a.to_dict() for a in self.alerts],
        }
        tmp = self.dir / "state.json.tmp"
        tmp.write_text(json.dumps(state, ensure_ascii=False, default=str))
        tmp.replace(self.dir / "state.json")


def run_live(symbol: str, horizon: int, feed_name: str, models_dir: Path, runtime_dir: Path,
             iterations: int = 0) -> int:
    """Bucle real en el PC del usuario: una evaluación por minuto, sin dinero real."""
    from ..notify import build_notifiers
    from ..research.news import load_calendar_csv
    from ..signals.registry import ModelBundle
    from .feeds import BinancePollingFeed

    load_dotenv()
    s = Settings.from_env()
    inst = get_instrument(symbol)
    cands = sorted(Path(models_dir).glob(f"{inst.symbol}_h{horizon}_*.pkl"))
    if not cands:
        print(f"No hay modelo entrenado para {inst.symbol} h={horizon}. Ejecute: tbot train --symbol {inst.symbol}")
        return 2
    bundle = ModelBundle.load(cands[0])
    if feed_name != "binance" or inst.source != "binance":
        print("Por ahora el feed en vivo implementado es Binance (cripto). Para divisas se requiere una API con "
              "cuenta (Deriv, OANDA, MT5 o IB) — ver docs/03_fase2_intermediarios.md.")
        return 2
    feed = BinancePollingFeed(inst.symbol)
    cal = load_calendar_csv(s.calendar_csv) if s.calendar_csv else None
    engine = SignalEngine(bundle, s, inst, price_source="Binance spot (API pública)", calendar=cal)
    loop = AlertLoop(engine, feed, build_notifiers(s, runtime_dir), runtime_dir, s)
    print(f"Modelo {bundle.model_id} — validación: {bundle.validation_status}. Sin dinero real.")
    i = 0
    while iterations == 0 or i < iterations:
        now = utcnow()
        nxt = (now + timedelta(minutes=1)).replace(second=0, microsecond=0) + timedelta(seconds=s.feed_latency_s)
        time.sleep(max(0.0, (nxt - now).total_seconds()))
        try:
            loop.step()
        except Exception as exc:  # desconexión o error de datos: se registra y se continúa
            print(f"Error en el ciclo ({exc}); se reintenta en el próximo minuto.", flush=True)
        i += 1
    return 0
