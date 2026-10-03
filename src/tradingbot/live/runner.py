"""Bucle de alertas: genera, notifica, registra tiempos y evalúa cada alerta al vencer.

Registro de eventos (runtime/<dir>/events.jsonl, solo lo escribe `tbot live`), una línea por evento:
  generated  → alerta creada (incluye la hora de recepción de los datos usados)
  sent       → notificada por un canal
  evaluated  → resultado conocido tras el vencimiento (o «no_evaluable» con su motivo)
  started / stopped / gap / cycle_failed / price_failed / state_write_failed → estado del propio bucle
La confirmación del usuario en el panel («received») va en runtime/<dir>/acks.jsonl (la escribe solo
`tbot serve`), para que cada archivo tenga un único escritor.
`state.json` es una instantánea para el panel web.
"""

from __future__ import annotations

import os
import time
from collections import deque
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from .. import jsonutil
from ..config import Settings, load_dotenv
from ..execution.paper import PaperLedger, read_rows
from ..instruments import get_instrument
from ..research.contracts import BinaryContract
from ..signals.alert import EXPERIMENTAL, NO_SIGNAL, PAUSED, SIGNAL, Alert
from ..signals.engine import RiskState, SignalEngine
from ..signals.monitor import evaluate_monitor
from ..signals.registry import OBSERVED, apply_policy, load_observation, policy_of
from ..timeutil import BOGOTA, utcnow

LIVE_METHOD = "precio real de entrada y vencimiento"
# Los ciclos despiertan con un desfase de milisegundos (y las consultas HTTP tardan distinto): el precio de
# vencimiento puede llegar un poco ANTES del minuto exacto. Hasta este margen se evalúa igual y se anota la
# duración real medida; más temprano, la alerta sigue pendiente.
EARLY_TOLERANCE_S = 2.0
GAP_S = 90.0  # dos ciclos separados por más de esto → evento «gap» (suspensión, cierre, red caída…)


def is_pending(alert: Alert) -> bool:
    """Alertas que se evalúan al vencer: SEÑAL, EXPERIMENTAL y PAUSADO que habría sido alerta."""
    return _evaluable(alert.status, alert.direction)


def _evaluable(status: str | None, direction: str | None) -> bool:
    return status in (SIGNAL, EXPERIMENTAL) or (status == PAUSED and direction is not None)


class EventLog:
    def __init__(self, runtime_dir: Path):
        self.dir = Path(runtime_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.path = self.dir / "events.jsonl"
        self.failed = 0  # escrituras perdidas (archivo bloqueado por otro programa, disco lleno…)

    def write(self, event: str, alert: Alert | None = None, **extra) -> None:
        """Nunca lanza: un evento perdido no debe detener el ciclo ni dejar una alerta a medio evaluar."""
        row = {"event": event, "time": utcnow().isoformat()}
        if alert is not None:
            row["alert_id"] = alert.alert_id
        row.update(extra)
        try:
            jsonutil.append_line(self.path, jsonutil.dumps(row, default=str))
        except OSError:
            self.failed += 1

    def unevaluated_ids(self) -> list[str]:
        """Alertas generadas que debían evaluarse y no tienen evento «evaluated» (p. ej. tras un reinicio)."""
        open_ids: dict[str, None] = {}
        for e in jsonutil.iter_jsonl(self.path):
            if not isinstance(e, dict):
                continue
            aid = e.get("alert_id")
            if e.get("event") == "generated" and aid:
                if _evaluable(e.get("status"), (e.get("payload") or {}).get("direction")):
                    open_ids[aid] = None
            elif e.get("event") == "evaluated" and aid:
                open_ids.pop(aid, None)
        return list(open_ids)

    def no_evaluable_summary(self, model_id: str) -> dict:
        """Alertas de `model_id` que no llegaron al libro («no_evaluable»), agrupadas por motivo."""
        ids: set[str] = set()
        reasons: dict[str, int] = {}
        for e in jsonutil.iter_jsonl(self.path):
            if not isinstance(e, dict):
                continue
            if e.get("event") == "generated" and (e.get("payload") or {}).get("model_id") == model_id:
                ids.add(e.get("alert_id"))
            elif e.get("event") == "evaluated" and e.get("alert_id") in ids:
                out = e.get("outcome") or {}
                if out.get("resultado") == "no_evaluable":
                    key = _reason_group(out.get("motivo", ""))
                    reasons[key] = reasons.get(key, 0) + 1
        return {"total": sum(reasons.values()), "por_motivo": reasons}


def _reason_group(motivo: str) -> str:
    """Motivo sin cifras («duración real 48.3 s …» → «duración real fuera de rango»), para agrupar."""
    for prefix, group in (("duración real", "duración real fuera de rango"), ("reinicio", "reinicio")):
        if motivo.startswith(prefix):
            return group
    return motivo.split(" (")[0]


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
        self.last_step_at: datetime | None = None
        self.last_ok_at: datetime | None = None  # hora real del último ciclo completo (para el panel)
        self.last_error: dict | None = None
        self.started_at = self.clock()
        self.status_counts: dict[str, int] = {}
        self.policy = policy_of(settings)  # se anota en cada fila del libro (Aclaración 2)
        self._decided: deque = deque(maxlen=120)  # velas ya usadas para una alerta evaluable
        self._resume()

    def _resume(self) -> None:
        """Tras un reinicio: recupera resultados del mismo modelo y cierra las alertas que quedaron abiertas."""
        bad = self.ledger.reload(self.engine.b.model_id)
        if bad:
            self.log.write("ledger_damaged_lines", lineas=bad)
        for t in self.ledger.trades:
            self.outcomes.append({"win": bool(t["win"]), "tie": bool(t["tie"]), "prob": t.get("prob")})
        if self.outcomes:
            self.monitor = evaluate_monitor(self.outcomes, self._breakeven(self.ledger.trades[-1].get("breakeven")))
        in_ledger = {r.get("alert_id"): r for r in read_rows(self.ledger.path)[0]}
        for aid in self.log.unevaluated_ids():
            row = in_ledger.get(aid)
            if row:  # se registró en el libro pero el programa se cortó antes de anotar el evento
                out = {"resultado": "empate" if row.get("tie") else ("acierto" if row.get("win") else "fallo"),
                       "metodo": row.get("method"), "recuperado_del_libro": True}
            else:
                out = {"resultado": "no_evaluable", "motivo": "reinicio: el programa se detuvo antes del vencimiento"}
            self.log.write("evaluated", alert_id=aid, evaluated_at=self.started_at, outcome=out)

    @staticmethod
    def _breakeven(be: float | None) -> float:
        return be if be and be <= 1 else 0.5

    # ------------------------------------------------------------------ ciclo
    def step(self, now_utc: datetime | None = None) -> Alert:
        now = now_utc or self.clock()
        if self.last_step_at is not None and (now - self.last_step_at).total_seconds() > GAP_S:
            self.log.write("gap", desde=self.last_step_at, hasta=now,
                           segundos=round((now - self.last_step_at).total_seconds()))
        self.last_step_at = now
        bars, received_at = self.feed.get(now)
        # Precio real «ahora» (si la fuente lo ofrece): salida de alertas que vencen y entrada de las nuevas.
        live_px, px_time = None, None
        if hasattr(self.feed, "current_price"):
            try:
                live_px, px_time = self.feed.current_price(now)
            except Exception as exc:  # sin precio en vivo: esas alertas quedarán no evaluables
                self.log.write("price_failed", error=str(exc))
        if len(bars):
            self.last_data_time = bars.index[-1] + pd.Timedelta(minutes=1)
        self._evaluate_pending(bars, now, live_px, px_time=px_time)
        alert = self.engine.evaluate(bars, now, self.risk, self.monitor.status)
        if is_pending(alert) and alert.decision_time in self._decided:
            # Faltó la vela nueva y el motor repetiría la decisión del minuto anterior con 60 s de retraso.
            alert.status, alert.direction = NO_SIGNAL, None
            alert.no_signal_reason = "decisión repetida: no llegó la vela nueva de este minuto"
        if is_pending(alert):
            self._decided.append(alert.decision_time)
        if is_pending(alert) and live_px is not None:
            # Hora en que se obtuvo el precio (incluye la demora de la consulta), no la del inicio del ciclo.
            alert.entry_price_live, alert.entry_time_live = float(live_px), px_time or now
        alert.clock_offset_s = getattr(self.feed, "offset_s", None)
        alert.generated_at = now
        self.log.write("generated", alert, data_received_at=received_at, status=alert.status,
                       payload=alert.to_dict())
        if alert.status in (SIGNAL, EXPERIMENTAL):
            for n in self.notifiers:
                try:
                    t0 = utcnow()
                    n.send(alert)
                    # Hora de envío en el reloj del bucle (real o simulado) + duración real del envío.
                    t = now + (utcnow() - t0)
                    alert.sent_at = alert.sent_at or t
                    self.log.write("sent", alert, channel=n.name, sent_at=t)
                except Exception as exc:  # un canal caído no detiene el sistema
                    self.log.write("send_failed", alert, channel=n.name, error=str(exc))
        elif alert.status != self.last_status:
            # «SIN SEÑAL» y «PAUSADO» se registran; en consola solo se imprime cuando cambia el estado.
            for n in self.notifiers:
                if n.name == "console":
                    print(f"{alert.one_line()} — {alert.no_signal_reason}", flush=True)
        if is_pending(alert):
            self.pending.append(alert)
        self.last_status = alert.status
        self.status_counts[alert.status] = self.status_counts.get(alert.status, 0) + 1
        self.alerts.appendleft(alert)
        self.last_ok_at = utcnow()
        self.write_state()
        return alert

    def note_error(self, exc: Exception, now: datetime | None = None) -> None:
        """Error de un ciclo: queda en events.jsonl y en el panel (no solo en la consola).

        Nunca lanza: si el propio registro falla (archivo bloqueado, disco lleno), el bucle sigue y
        reintenta en el próximo minuto.
        """
        now = now or utcnow()
        self.last_error = {"time": now.isoformat(), "error": f"{type(exc).__name__}: {exc}"}
        try:
            self.log.write("cycle_failed", error=self.last_error["error"])
        except Exception:  # noqa: BLE001
            pass
        try:
            self.write_state()
        except Exception:  # noqa: BLE001 — el panel mostrará los datos como desactualizados
            pass

    def _record(self, a: Alert, side: int, d: float, o: float, c: float, pnl: float, method: str,
                extra: dict | None = None) -> None:
        tie, win = d == 0, d == side
        a.outcome = {"resultado": "empate" if tie else ("acierto" if win else "fallo"), "metodo": method,
                     "entrada": round(float(o), 6), "salida": round(float(c), 6), "pnl": round(pnl, 4),
                     **(extra or {})}
        shadow = a.status != SIGNAL
        # Lo que la Aclaración 2 (punto 7) exige reportar viaja con cada fila del libro.
        meas = {"policy": self.policy, "decision_time": a.decision_time.isoformat(),
                "hora_bogota": a.decision_time.astimezone(BOGOTA).hour,
                "duracion_real_s": (extra or {}).get("duracion_real_s"), "retraso_s": (extra or {}).get("retraso_s"),
                # entry_time_live ya está en hora de la fuente (Binance), igual que decision_time.
                "entrada_tras_cierre_s": (round((pd.Timestamp(a.entry_time_live) - pd.Timestamp(a.decision_time))
                                                .total_seconds(), 3) if a.entry_time_live else None),
                "desfase_reloj_s": a.clock_offset_s}
        self.ledger.record(a, pnl, bool(tie), bool(win), shadow, method=method, extra=meas)
        if not shadow:
            self.risk.register_outcome(pnl)
        self.outcomes.append({"win": bool(win), "tie": bool(tie), "prob": a.prob})
        self.monitor = evaluate_monitor(self.outcomes, self._breakeven(a.breakeven))

    def _pnl(self, side: int, d: float, o: float, c: float) -> float:
        if isinstance(self.engine.contract, BinaryContract):
            return float(self.engine.contract.pnl(np.array([side]), np.array([d]))[0])
        return float(side * (c - o)) / o * 1e4 - float(self.engine.contract.cost_bps(
            np.array([o]), np.array([0.0]))[0])

    def _evaluate_pending(self, bars: pd.DataFrame, now: datetime, live_px: float | None = None,
                          max_late_s: float = 10.0, px_time: datetime | None = None) -> None:
        live_mode = hasattr(self.feed, "current_price")
        still = []
        for a in self.pending:
            side = 1 if a.direction == "sube" else -1
            if a.entry_price_live is not None:
                # Evaluación con precios REALES de entrada y de vencimiento (incluye la latencia real).
                # ¿Es este el ciclo del vencimiento? Se decide con el reloj del ciclo, que solo varía en
                # milisegundos; las horas de los precios arrastran la demora variable de las consultas HTTP.
                due = pd.Timestamp(a.generated_at or a.entry_time_live) + pd.Timedelta(minutes=a.duration_min)
                if (pd.Timestamp(now) - due).total_seconds() < -EARLY_TOLERANCE_S:
                    still.append(a)
                    continue
                exit_t = pd.Timestamp(px_time or now)
                dur = (exit_t - pd.Timestamp(a.entry_time_live)).total_seconds()
                dev = dur - 60.0 * a.duration_min  # >0: el precio de vencimiento llegó tarde; <0: temprano
                if live_px is None:
                    a.outcome = {"resultado": "no_evaluable", "motivo": "sin precio al vencer (falló la consulta)"}
                elif abs(dev) > max_late_s:
                    a.outcome = {"resultado": "no_evaluable",
                                 "motivo": f"duración real {dur:.1f} s entre los precios de entrada y de vencimiento "
                                           f"(debía ser {60 * a.duration_min} ± {max_late_s:.0f} s)"}
                else:
                    o, c = a.entry_price_live, float(live_px)
                    d = np.sign(round((c - o) / (self.engine.inst.point / 2)))
                    self._record(a, side, d, o, c, self._pnl(side, d, o, c), LIVE_METHOD,
                                 {"duracion_real_s": round(dur, 3), "retraso_s": round(dev, 3)})
                a.evaluated_at = now
                self.log.write("evaluated", a, outcome=a.outcome, evaluated_at=now)
                continue
            if live_mode:
                # En vivo, sin precio real de entrada no se usa el método optimista de velas (sesgaría el veredicto).
                a.outcome = {"resultado": "no_evaluable", "motivo": "sin precio real de entrada (falló la consulta)"}
                a.evaluated_at = now
                self.log.write("evaluated", a, outcome=a.outcome, evaluated_at=now)
                continue
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
                if isinstance(self.engine.contract, BinaryContract):
                    pnl = float(self.engine.contract.pnl(np.array([side]), np.array([d]))[0])
                else:
                    sp = bars.at[entry_t, "spread_o"] / 2 + bars.at[exit_t, "spread_c"] / 2
                    pnl = float(side * (c - o) - sp) / o * 1e4
                self._record(a, side, d, o, c, pnl, "velas (optimista: entrada en la apertura)")
            a.evaluated_at = now
            self.log.write("evaluated", a, outcome=a.outcome, evaluated_at=now)
        self.pending = still

    # ------------------------------------------------------------------ estado para el panel
    def write_state(self) -> None:
        counts = dict(self.status_counts)
        b = self.engine.b
        trades = self.ledger.trades
        state = {
            "updated_at": utcnow().isoformat(),
            # Hora real del último ciclo completo: si los ciclos fallan, updated_at avanza pero esta no.
            "last_ok_at": self.last_ok_at.isoformat() if self.last_ok_at else None,
            "started_at": self.started_at.isoformat(),
            "settings": self.s.public_dict(),
            "model": {"model_id": b.model_id, "validation_status": b.validation_status,
                      "validation_evidence": evidence_summary(b.validation_evidence), "synthetic": b.synthetic,
                      "trained_from": b.trained_from, "trained_to": b.trained_to},
            "monitor": self.monitor.to_dict(),
            "last_data_time": self.last_data_time.isoformat() if self.last_data_time is not None else None,
            "last_error": self.last_error,
            "eventos_no_escritos": self.log.failed,
            "counts": counts,
            "paper": {"balance": self.ledger.balance, "n": sum(1 for t in trades if not t["shadow"]),
                      "shadow_n": sum(1 for t in trades if t["shadow"]),
                      "shadow_pnl": sum(t["pnl"] for t in trades if t["shadow"])},
            "alerts": [a.to_dict() for a in self.alerts],
        }
        # Temporal propio de este proceso; en Windows el reemplazo falla si el panel está leyendo justo ahora.
        tmp = self.dir / f"state.json.{os.getpid()}.tmp"
        tmp.write_text(jsonutil.dumps(state, default=str), encoding="utf-8")
        for _ in range(20):
            try:
                tmp.replace(self.dir / "state.json")
                return
            except PermissionError:
                time.sleep(0.05)
        tmp.unlink(missing_ok=True)
        self.log.write("state_write_failed", error="state.json ocupado; se reintenta en el próximo ciclo")


def evidence_summary(evidence: dict) -> dict:
    """Evidencia de validación resumida para el panel (el veredicto completo tiene cientos de campos)."""
    out = dict(evidence or {})
    hv = out.get("holdout")
    if isinstance(hv, dict):
        out["holdout"] = {"verdict": hv.get("verdict"), "passed": hv.get("passed", [])}
    return jsonutil.finite(out)


class RuntimeLock:
    """Impide dos `tbot live` sobre la misma carpeta (cada resultado se contaría dos veces).

    Bloqueo del sistema operativo sobre un archivo abierto: si el proceso muere, se libera solo.
    """

    def __init__(self, runtime_dir: Path):
        self.path = Path(runtime_dir) / "live.lock"
        self.fh = None

    def acquire(self) -> bool:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fh = open(self.path, "a+")
        try:
            if os.name == "nt":
                import msvcrt

                fh.seek(0)
                msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            fh.close()
            return False
        self.fh = fh
        return True

    def release(self) -> None:
        if self.fh is None:
            return
        try:
            if os.name == "nt":
                import msvcrt

                self.fh.seek(0)
                msvcrt.locking(self.fh.fileno(), msvcrt.LK_UNLCK, 1)
        except OSError:
            pass
        self.fh.close()
        self.fh = None


def keep_awake(on: bool) -> bool:
    """Windows: evita que el equipo se suspenda por inactividad mientras corre `tbot live`.

    Es una petición temporal del proceso (como la de un reproductor de video), no un cambio de la
    configuración de energía; se retira al salir. No impide cerrar la tapa ni la suspensión manual.
    """
    if os.name != "nt":
        return False
    try:
        import ctypes

        fn = ctypes.windll.kernel32.SetThreadExecutionState
        fn.argtypes, fn.restype = [ctypes.c_uint32], ctypes.c_uint32  # 0x80000000 no cabe en un int con signo
        es_continuous, es_system_required = 0x80000000, 0x00000001
        return bool(fn(es_continuous | (es_system_required if on else 0)))
    except Exception:  # noqa: BLE001
        return False


def check_clock(feed, log: EventLog, latency_s: float) -> float | None:
    """Mide y registra el desfase PC–Binance. El bucle lo corrige (programa los ciclos y decide qué vela
    está cerrada con la hora de Binance); si es grande, además avisa."""
    try:
        off = feed.clock_offset()
        log.write("clock_offset", segundos=round(off, 3))
    except Exception:  # noqa: BLE001 — sin red: se conserva el último desfase medido
        return None
    if abs(off) > 5:
        print(f"Aviso: el reloj del PC difiere {off:+.1f} s del de Binance (se corrige, pero conviene "
              "sincronizar la hora de Windows: Configuración → Hora e idioma → Sincronizar ahora).", flush=True)
    return off


def run_live(symbol: str, horizon: int, feed_name: str, models_dir: Path, runtime_dir: Path,
             iterations: int = 0, model: str | None = None) -> int:
    """Bucle real en el PC del usuario: una evaluación por minuto, sin dinero real."""
    from ..notify import build_notifiers
    from ..research.news import load_calendar_csv
    from ..signals.registry import ModelBundle
    from .feeds import BinancePollingFeed

    load_dotenv()
    s = Settings.from_env()
    inst = get_instrument(symbol)
    pattern = f"{inst.symbol}_h{horizon}_{model}.pkl" if model else f"{inst.symbol}_h{horizon}_*.pkl"
    cands = sorted(Path(models_dir).glob(pattern))
    if not cands:
        print(f"No hay modelo entrenado para {inst.symbol} h={horizon}{' ' + model if model else ''}. Ejecute: "
              f"tbot train --symbol {inst.symbol} --horizon {horizon} --model {model or 'gbm'}")
        return 2
    if len(cands) > 1:
        print(f"Hay varios modelos para {inst.symbol} h={horizon}: {', '.join(c.name for c in cands)}. "
              "Indique cuál con --model (p. ej. --model gbm).")
        return 2
    bundle = ModelBundle.load(cands[0])
    if feed_name != "binance" or inst.source != "binance":
        print("Por ahora el feed en vivo implementado es Binance (cripto). Para divisas se requiere una API con "
              "cuenta (Deriv, OANDA, MT5 o IB) — ver docs/03_fase2_intermediarios.md.")
        return 2
    if bundle.validation_status in OBSERVED:
        # Observación pre-registrada (Aclaración 2): entrenamiento exacto y política fija, no la del .env.
        obs = load_observation()
        if not obs or obs.get("model_id") != bundle.model_id:
            print(f"El modelo {bundle.model_id} no es el registrado para la observación en vivo "
                  f"({(obs or {}).get('model_id', 'no hay config/observacion_en_vivo.json')}). Si reentrenó, "
                  "registre primero una enmienda con fecha (ver docs/01, Aclaración 2); si no, restaure el modelo.")
            return 2
        for change in apply_policy(s, obs["policy"]):
            print(f"Política registrada aplicada (se ignora el .env): {change}")
    lock = RuntimeLock(runtime_dir)
    if not lock.acquire():
        print(f"Ya hay un «tbot live» usando la carpeta {runtime_dir}. Ciérrelo antes de abrir otro "
              "(dos a la vez contarían cada resultado dos veces).")
        return 2
    try:
        feed = BinancePollingFeed(inst.symbol)
        cal = load_calendar_csv(s.calendar_csv) if s.calendar_csv else None
        engine = SignalEngine(bundle, s, inst, price_source="Binance spot (API pública)", calendar=cal)
        # Todo el bucle (hora del ciclo, antigüedad de los datos, entrada y vencimiento) usa la hora de
        # Binance: el reloj de este PC se atrasa ~0,25 s/h con el servicio de hora de Windows detenido.
        loop = AlertLoop(engine, feed, build_notifiers(s, runtime_dir), runtime_dir, s, clock=feed.server_now)
        loop.log.write("started", model_id=bundle.model_id, validation_status=bundle.validation_status,
                       pid=os.getpid())
        print(f"Modelo {bundle.model_id} — validación: {bundle.validation_status}. Sin dinero real.")
        if loop.ledger.trades:
            print(f"Se recuperaron {len(loop.ledger.trades)} resultados ya registrados de este modelo.")
        if keep_awake(True):
            print("Mientras esté abierto, Windows no se suspenderá por inactividad (deje el cargador conectado).")
        i = 0
        while iterations == 0 or i < iterations:
            if i % 60 == 0:  # cada hora se vuelve a medir el desfase del reloj del PC frente al de Binance
                check_clock(feed, loop.log, s.feed_latency_s)
            # El ciclo se programa con la hora de Binance: TB_FEED_LATENCY_S después del cierre de la vela.
            now = feed.server_now()
            nxt = (now + timedelta(minutes=1)).replace(second=0, microsecond=0) + timedelta(seconds=s.feed_latency_s)
            time.sleep(max(0.0, (nxt - now).total_seconds()))
            try:
                loop.step()
            except Exception as exc:  # desconexión o error de datos: se registra y se continúa
                loop.note_error(exc)
                print(f"Error en el ciclo ({exc}); se reintenta en el próximo minuto.", flush=True)
            i += 1
        return 0
    except KeyboardInterrupt:
        print("Detenido por el usuario.")
        return 0
    finally:
        try:
            EventLog(runtime_dir).write("stopped")
        except Exception:  # noqa: BLE001 — no ocultar el error original ni impedir liberar el bloqueo
            pass
        keep_awake(False)
        lock.release()
