"""Motor de decisión: convierte el estado del mercado en una alerta o en «SIN SEÑAL».

Una alerta accionable («SEÑAL») exige TODO lo siguiente:
  1. modelo con estado VALIDADO (desarrollo + periodo bloqueado + observación en vivo);
  2. datos frescos, historial suficiente y horario permitido;
  3. sin ventanas de noticias programadas/calendario durante la operación y spread normal;
  4. EV neto estimado ≥ margen y límite inferior del intervalo de probabilidad > umbral de rentabilidad;
  5. límites de riesgo no alcanzados y monitor de deterioro sin pausa.
Si falla cualquiera → «SIN SEÑAL» con el motivo (o «EXPERIMENTAL — NO OPERAR» si el usuario activó
TB_SHOW_EXPERIMENTAL y el único fallo es la validación).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from ..config import Settings
from ..instruments import Instrument
from ..research.contracts import BinaryContract, SpotContract
from ..research.features import FEATURES, compute_features, rolling_abs_move
from ..research.labels import make_labels
from ..research.models import explain_logit
from ..research.news import SCHEDULED_RELEASES, calendar_blackout, trade_overlaps_window
from ..research.simulate import max_age_for_horizon
from ..timeutil import BOGOTA, fmt_bogota
from .alert import EXPERIMENTAL, NO_SIGNAL, PAUSED, SIGNAL, Alert
from .registry import ACTIONABLE, ModelBundle

MIN_HISTORY = 300


@dataclass
class RiskState:
    day: str = ""
    alerts_today: int = 0
    pnl_today: float = 0.0
    consecutive_losses: int = 0
    history: list = field(default_factory=list)

    def roll(self, now_utc: datetime) -> None:
        d = now_utc.astimezone(BOGOTA).date().isoformat()
        if d != self.day:
            self.day, self.alerts_today, self.pnl_today = d, 0, 0.0

    def register_outcome(self, pnl: float) -> None:
        self.pnl_today += pnl
        self.consecutive_losses = self.consecutive_losses + 1 if pnl < 0 else (0 if pnl > 0 else self.consecutive_losses)


def _next_release_text(start: pd.Timestamp, minutes: int) -> str | None:
    """Próxima hora de publicación programada entre `start` y `start + minutes`."""
    for tz, hh, mm in SCHEDULED_RELEASES:
        local = start.tz_convert(tz)
        rel = local.normalize() + pd.Timedelta(hours=hh, minutes=mm)
        if local.dayofweek < 5 and start <= rel.tz_convert("UTC") <= start + pd.Timedelta(minutes=minutes):
            return f"{rel.tz_convert('America/Bogota'):%H:%M} Bogotá ({hh:02d}:{mm:02d} {tz})"
    return None


class SignalEngine:
    def __init__(self, bundle: ModelBundle, settings: Settings, inst: Instrument, price_source: str,
                 calendar: pd.DataFrame | None = None):
        self.b = bundle
        self.s = settings
        self.inst = inst
        self.price_source = price_source
        self.calendar = calendar
        self.h = bundle.horizon
        if settings.contract == "binaria":
            self.contract = BinaryContract(settings.payout, settings.tie_rule)
        else:
            self.contract = SpotContract(commission_px=inst.commission_px, commission_bps=inst.commission_bps)

    def _base(self, decision_time: datetime) -> Alert:
        return Alert(instrument=self.inst.label, status=NO_SIGNAL, price_source=self.price_source,
                     broker=self.s.broker, decision_time=decision_time, duration_min=self.h,
                     contract=self.s.contract, payout=self.s.payout if self.s.contract == "binaria" else None,
                     payout_verified=self.s.payout_verified, model_id=self.b.model_id,
                     validation_status=self.b.validation_status,
                     ev_units="unidades de apuesta" if self.s.contract == "binaria" else "pb")

    def evaluate(self, bars: pd.DataFrame, now_utc: datetime, risk: RiskState, monitor_status: str = "OK") -> Alert:
        valid = bars[bars["c"].notna()]
        if valid.empty:
            a = self._base(now_utc)
            a.no_signal_reason = "sin datos"
            return a
        last_t = valid.index[-1]
        decision_time = (last_t + pd.Timedelta(minutes=1)).to_pydatetime()
        a = self._base(decision_time)
        risk.roll(now_utc)

        # 1) Frescura e historial.
        age = (now_utc - decision_time).total_seconds()
        if age > self.s.max_staleness_s:
            a.no_signal_reason = f"datos desactualizados: última vela cerró hace {age:.0f} s"
            return a
        if len(valid) < MIN_HISTORY:
            a.no_signal_reason = f"historial insuficiente ({len(valid)} < {MIN_HISTORY} velas)"
            return a
        feats = compute_features(bars)
        x = feats.iloc[[-1]]
        if x[FEATURES].isna().any(axis=None):
            a.no_signal_reason = "variables incompletas (hueco reciente en los datos)"
            return a

        # 2) Predicción calibrada.
        p_up = float(self.b.predict_p_up(x)[0])
        side = 1 if p_up >= 0.5 else -1
        p_dir = p_up if side > 0 else 1 - p_up
        lo, hi, n = self.b.calibrator.interval(np.array([p_dir]))
        lo, hi, n = float(lo[0]), float(hi[0]), int(n[0])
        edges = self.b.calibrator.edges
        bi = int(np.clip(np.searchsorted(edges, p_dir, side="right") - 1, 0, len(edges) - 2))
        hist_hit = self.b.calibrator.bin_hits[bi] / max(self.b.calibrator.bin_n[bi], 1)
        max_age = max_age_for_horizon(self.h)
        a.direction = "sube" if side > 0 else "baja"
        a.act_before = decision_time + timedelta(seconds=max_age)
        a.prob, a.prob_lo, a.prob_hi, a.prob_n = p_dir, lo, hi, n

        c_now = float(valid["c"].iloc[-1])
        spread_now = float(valid["spread_c"].iloc[-1])
        lab = make_labels(valid.iloc[-1440:], self.h, 1, self.inst.point)
        q_tie = float(np.nanmean((lab["dir"] == 0).where(lab["dir"].notna()))) if lab["dir"].notna().any() else 0.0

        # 3) Costos y valor esperado.
        if isinstance(self.contract, BinaryContract):
            be = self.contract.breakeven(q_tie)
            ev = float(self.contract.ev(np.array([p_dir]), np.array([q_tie]))[0])
            b_min = (1 - p_dir) / p_dir if p_dir > 0 else float("inf")
            a.costs = {"pago_supuesto": f"{self.s.payout:.0%}", "empates_recientes": f"{q_tie:.1%}",
                       "regla_empate": self.s.tie_rule}
            ev_ok = ev >= self.s.ev_margin
            ev_txt = (f"EV = (1−q)·(p·pago − (1−p)) + q·empate = {ev:+.4f} con p={p_dir:.3f}, "
                      f"pago={self.s.payout:.2f}, q={q_tie:.3f}")
            a.invalidators.append(f"Pago ofrecido menor que {b_min:.0%} (con p={p_dir:.1%} el EV sería ≤ 0).")
        else:
            m_hat = float(rolling_abs_move(valid, self.h).iloc[-1] / c_now * 1e4)
            cost = float(self.contract.cost_bps(np.array([c_now]), np.array([spread_now]))[0])
            be = SpotContract.breakeven(m_hat, cost)
            ev = float(self.contract.ev_bps(np.array([p_dir]), np.array([m_hat]), np.array([cost]))[0])
            a.costs = {"spread_pb": f"{spread_now / c_now * 1e4:.2f}", "comisión_pb":
                       f"{(self.inst.commission_px / c_now * 1e4 + self.inst.commission_bps):.2f}",
                       "movimiento_medio_pb": f"{m_hat:.2f}"}
            ev_ok = ev >= self.s.spot_ev_margin_frac * cost
            ev_txt = f"EV ≈ (2p−1)·m − c = {ev:+.3f} pb (p={p_dir:.3f}, m={m_hat:.2f} pb, c={cost:.2f} pb)"
        a.ev, a.breakeven = ev, be

        # 4) Razones cuantificables.
        a.reasons.append(f"Probabilidad calibrada {p_dir:.1%}; en calibración, {n} señales de confianza similar "
                         f"acertaron {hist_hit:.1%}.")
        a.reasons.append(ev_txt)
        if self.b.model_name == "logit":
            for name, contrib in explain_logit(self.b.model, x.iloc[0]):
                a.reasons.append(f"{name} = {x.iloc[0][name]:+.2f} (contribución al logit {contrib:+.3f})")
        else:
            for name in ("r0", "cum15", "rsi14", "spread_rel"):
                a.reasons.append(f"{name} = {x.iloc[0][name]:+.2f}")

        # 5) Factores que invalidarían la señal.
        a.invalidators.append(f"No entrar después de {fmt_bogota(a.act_before)} (vigencia {max_age:.0f} s).")
        vol1 = float(np.exp(x.iloc[0]["lvol60"])) * c_now
        a.invalidators.append(f"Precio de entrada a más de {0.5 * vol1:.{self._dec()}f} del cierre de referencia "
                              f"{c_now:.{self._dec()}f}.")
        sp_med = spread_now / x.iloc[0]["spread_rel"] if x.iloc[0]["spread_rel"] > 0 else spread_now
        a.invalidators.append(f"Spread del intermediario mayor que {2 * sp_med:.{self._dec()}f}.")
        rel = _next_release_text(pd.Timestamp(decision_time), self.h + 15)
        if rel:
            a.invalidators.append(f"Publicación programada cercana: {rel}.")

        # 6) Filtros → «SIN SEÑAL».
        blockers = []
        hb = decision_time.astimezone(BOGOTA).hour
        h0, h1 = self.s.allowed_hours_bogota
        if not (h0 <= hb < h1):
            blockers.append(f"fuera del horario permitido ({h0}–{h1} h Bogotá)")
        grid = pd.date_range(last_t - pd.Timedelta(minutes=5), last_t + pd.Timedelta(minutes=self.h + 2), freq="min")
        pos = grid.get_loc(last_t)
        if trade_overlaps_window(grid, 1, self.h)[pos]:
            blockers.append("ventana de publicación programada durante la operación")
        if self.calendar is not None:
            ccy = {self.inst.symbol[:3], self.inst.symbol[3:6]}
            ev_cal = calendar_blackout(pd.Timestamp(decision_time), self.h, self.calendar, ccy)
            if not ev_cal.empty:
                blockers.append(f"evento de calendario: {ev_cal.iloc[0]['title']}")
        if x.iloc[0]["spread_rel"] > 3:
            blockers.append(f"spread anormal ({x.iloc[0]['spread_rel']:.1f}× su mediana)")
        if risk.alerts_today >= self.s.max_alerts_per_day:
            blockers.append("límite diario de alertas alcanzado")
        if risk.pnl_today <= -abs(self.s.max_daily_loss):
            blockers.append("límite de pérdida diaria (simulada) alcanzado")
        if risk.consecutive_losses >= self.s.max_consecutive_losses:
            blockers.append("demasiadas pérdidas consecutivas")
        if not ev_ok:
            blockers.append(f"EV estimado {ev:+.4f} por debajo del margen exigido")
        if isinstance(self.contract, BinaryContract) and not lo > be:
            blockers.append(f"límite inferior de la probabilidad {lo:.1%} ≤ umbral {be:.1%}")
        if isinstance(self.contract, SpotContract) and be > 1:
            blockers.append(f"costo ≥ movimiento medio: umbral de acierto {be:.0%} inalcanzable")

        if monitor_status == "PAUSADO":
            a.status, a.no_signal_reason = PAUSED, "monitor de deterioro: resultados en vivo por debajo del umbral"
            return a
        validated = self.b.validation_status in ACTIONABLE and monitor_status == "OK"
        if blockers:
            a.status = NO_SIGNAL
            a.no_signal_reason = "; ".join(blockers)
            a.reasons.insert(0, f"Estimación del modelo: {a.direction} con {p_dir:.1%} (insuficiente para alertar).")
            a.direction = None
            return a
        if validated:
            a.status = SIGNAL
            risk.alerts_today += 1
            return a
        if self.s.show_experimental:
            a.status = EXPERIMENTAL
            return a
        a.status = NO_SIGNAL
        a.no_signal_reason = f"modelo sin validar (estado {self.b.validation_status})"
        a.direction = None
        return a

    def _dec(self) -> int:
        return max(0, int(round(-np.log10(self.inst.point))))
