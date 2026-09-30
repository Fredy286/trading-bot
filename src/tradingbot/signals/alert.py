"""Formato de las alertas y su ciclo de vida (generada → enviada → recibida → evaluada)."""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime

from ..timeutil import BOGOTA, fmt_bogota

# Estados posibles de una alerta.
SIGNAL = "SEÑAL"  # solo con modelo VALIDADO (pasó desarrollo, periodo bloqueado y observación en vivo)
EXPERIMENTAL = "EXPERIMENTAL — NO OPERAR"
NO_SIGNAL = "SIN SEÑAL"
PAUSED = "PAUSADO"
EXAMPLE = "EJEMPLO FICTICIO"


def fictitious_example() -> str:
    """Ejemplo de presentación exigido. NUNCA es una predicción real."""
    return ("EJEMPLO FICTICIO — EUR/USD | 15:00 America/Bogota | dirección: baja | duración: 1 minuto | "
            "probabilidad: no calculada | pago: no verificado | estado: NO OPERAR")


@dataclass
class Alert:
    instrument: str
    status: str
    price_source: str
    broker: str
    decision_time: datetime  # UTC: cierre de la vela usada
    duration_min: int
    direction: str | None = None  # "sube" | "baja"
    act_before: datetime | None = None  # UTC
    prob: float | None = None  # probabilidad calibrada de la dirección
    prob_lo: float | None = None
    prob_hi: float | None = None
    prob_n: int | None = None  # señales comparables en calibración
    breakeven: float | None = None
    contract: str = "binaria"
    payout: float | None = None
    payout_verified: bool = False
    costs: dict = field(default_factory=dict)
    ev: float | None = None
    ev_units: str = "unidades de apuesta"
    reasons: list[str] = field(default_factory=list)
    invalidators: list[str] = field(default_factory=list)
    no_signal_reason: str | None = None
    model_id: str | None = None
    validation_status: str | None = None
    alert_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    generated_at: datetime | None = None
    sent_at: datetime | None = None
    received_at: datetime | None = None
    evaluated_at: datetime | None = None
    outcome: dict | None = None

    # ------------------------------------------------------------------ serialización
    def to_dict(self) -> dict:
        d = asdict(self)
        for k, v in d.items():
            if isinstance(v, datetime):
                d[k] = v.isoformat()
        d["decision_time_bogota"] = fmt_bogota(self.decision_time)
        d["act_before_bogota"] = fmt_bogota(self.act_before) if self.act_before else None
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Alert":
        d = {k: v for k, v in d.items() if k in cls.__dataclass_fields__}
        for k in ("decision_time", "act_before", "generated_at", "sent_at", "received_at", "evaluated_at"):
            if d.get(k):
                d[k] = datetime.fromisoformat(d[k])
        return cls(**d)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)

    # ------------------------------------------------------------------ presentación
    def one_line(self) -> str:
        hora = self.decision_time.astimezone(BOGOTA).strftime("%H:%M")
        prob = "no calculada" if self.prob is None else f"{self.prob:.1%}"
        if self.prob is not None and self.prob_lo is not None:
            prob += f" [{self.prob_lo:.1%}–{self.prob_hi:.1%}]"
        pago = "no verificado" if not self.payout_verified else f"{self.payout:.0%}"
        if self.payout is not None and not self.payout_verified:
            pago = f"{self.payout:.0%} supuesto, no verificado"
        estado = "NO OPERAR" if self.status != SIGNAL else "SEÑAL (alerta, no orden)"
        if self.status == NO_SIGNAL:
            estado = "SIN SEÑAL"
        return (f"{self.instrument} | {hora} America/Bogota | dirección: {self.direction or '—'} | "
                f"duración: {self.duration_min} minuto{'s' if self.duration_min != 1 else ''} | probabilidad: {prob} | "
                f"pago: {pago} | estado: {estado}")

    def format_text(self) -> str:
        L = [f"[{self.status}] {self.instrument}"]
        L.append(f"Fecha y hora: {fmt_bogota(self.decision_time)}")
        L.append(f"Intermediario: {self.broker} | Fuente de precio: {self.price_source}")
        if self.status == NO_SIGNAL:
            L.append(f"Motivo: {self.no_signal_reason or 'no se cumplen los criterios'}")
        L.append(f"Dirección prevista: {self.direction or '—'} | Duración: {self.duration_min} min")
        if self.act_before:
            L.append(f"Actuar antes de: {fmt_bogota(self.act_before)}")
        if self.prob is not None:
            be = "—" if self.breakeven is None else f"{self.breakeven:.1%}"
            ic = "" if self.prob_lo is None else f" (IC90 del bin: {self.prob_lo:.1%}–{self.prob_hi:.1%}, n={self.prob_n})"
            L.append(f"Probabilidad calibrada: {self.prob:.1%}{ic} | Umbral de rentabilidad: {be}")
        else:
            L.append("Probabilidad: no calculada")
        if self.contract == "binaria":
            pv = "verificado" if self.payout_verified else "NO verificado con el intermediario"
            pago = "no definido" if self.payout is None else f"{self.payout:.0%}"
            L.append(f"Contrato: binaria | Pago: {pago} ({pv})")
        else:
            L.append("Contrato: contado/CFD")
        if self.costs:
            L.append("Costos considerados: " + ", ".join(f"{k}={v}" for k, v in self.costs.items()))
        if self.ev is not None:
            L.append(f"Valor esperado estimado: {self.ev:+.4f} {self.ev_units}")
        if self.reasons:
            L.append("Razones cuantificables:")
            L.extend(f"  - {r}" for r in self.reasons)
        if self.invalidators:
            L.append("Invalidaría la señal:")
            L.extend(f"  - {r}" for r in self.invalidators)
        L.append(f"Modelo: {self.model_id or '—'} | Validación: {self.validation_status or '—'}")
        return "\n".join(L)
