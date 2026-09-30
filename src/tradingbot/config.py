"""Configuración de ejecución mediante variables de entorno (prefijo TB_) o archivo `.env`.

Ningún secreto vive en el código: tokens y credenciales se leen del entorno. Ver `.env.example`.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def load_dotenv(path: str | Path = ".env") -> None:
    """Carga un archivo .env sencillo (CLAVE=valor) sin sobrescribir variables ya definidas."""
    p = Path(path)
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def _bool(v: str | None, default: bool = False) -> bool:
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "si", "sí", "yes", "y")


def _hours(v: str | None) -> tuple[int, int]:
    """'7-16' → (7, 16): horas de Bogotá permitidas [inicio, fin)."""
    if not v:
        return (0, 24)
    a, b = v.split("-")
    return (int(a), int(b))


@dataclass
class Settings:
    instruments: list[str] = field(default_factory=lambda: ["BTCUSDT"])
    horizon_min: int = 1
    allowed_hours_bogota: tuple[int, int] = (0, 24)
    broker: str = "ninguno (solo alertas)"
    contract: str = "binaria"  # binaria | contado
    payout: float = 0.85
    payout_verified: bool = False
    tie_rule: str = "refund"
    ev_margin: float = 0.02
    spot_ev_margin_frac: float = 0.25
    show_experimental: bool = False
    notify: list[str] = field(default_factory=lambda: ["console", "file"])
    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None
    webhook_url: str | None = None
    stake: float = 1.0
    max_alerts_per_day: int = 20
    max_daily_loss: float = 5.0
    max_consecutive_losses: int = 5
    feed_latency_s: float = 2.0
    max_staleness_s: float = 90.0
    calendar_csv: str | None = None
    runtime_dir: str = "runtime/live"

    @classmethod
    def from_env(cls, env: dict | None = None) -> "Settings":
        e = os.environ if env is None else env
        s = cls()
        if e.get("TB_INSTRUMENTS"):
            s.instruments = [x.strip().upper() for x in e["TB_INSTRUMENTS"].split(",") if x.strip()]
        s.horizon_min = int(e.get("TB_HORIZON_MIN", s.horizon_min))
        s.allowed_hours_bogota = _hours(e.get("TB_HOURS_BOGOTA"))
        s.broker = e.get("TB_BROKER", s.broker)
        s.contract = e.get("TB_CONTRACT", s.contract)
        s.payout = float(e.get("TB_PAYOUT", s.payout))
        s.payout_verified = _bool(e.get("TB_PAYOUT_VERIFIED"), False)
        s.tie_rule = e.get("TB_TIE_RULE", s.tie_rule)
        s.ev_margin = float(e.get("TB_EV_MARGIN", s.ev_margin))
        s.spot_ev_margin_frac = float(e.get("TB_SPOT_EV_MARGIN_FRAC", s.spot_ev_margin_frac))
        s.show_experimental = _bool(e.get("TB_SHOW_EXPERIMENTAL"), False)
        if e.get("TB_NOTIFY"):
            s.notify = [x.strip().lower() for x in e["TB_NOTIFY"].split(",") if x.strip()]
        s.telegram_bot_token = e.get("TB_TELEGRAM_BOT_TOKEN") or None
        s.telegram_chat_id = e.get("TB_TELEGRAM_CHAT_ID") or None
        s.webhook_url = e.get("TB_WEBHOOK_URL") or None
        s.stake = float(e.get("TB_STAKE", s.stake))
        s.max_alerts_per_day = int(e.get("TB_MAX_ALERTS_PER_DAY", s.max_alerts_per_day))
        s.max_daily_loss = float(e.get("TB_MAX_DAILY_LOSS", s.max_daily_loss))
        s.max_consecutive_losses = int(e.get("TB_MAX_CONSECUTIVE_LOSSES", s.max_consecutive_losses))
        s.feed_latency_s = float(e.get("TB_FEED_LATENCY_S", s.feed_latency_s))
        s.max_staleness_s = float(e.get("TB_MAX_STALENESS_S", s.max_staleness_s))
        s.calendar_csv = e.get("TB_CALENDAR_CSV") or None
        s.runtime_dir = e.get("TB_RUNTIME_DIR", s.runtime_dir)
        if s.contract not in ("binaria", "contado"):
            raise ValueError("TB_CONTRACT debe ser 'binaria' o 'contado'")
        if not 0 < s.payout < 5:
            raise ValueError("TB_PAYOUT fuera de rango")
        return s

    def public_dict(self) -> dict:
        """Configuración sin secretos (para mostrar en el panel)."""
        d = dict(self.__dict__)
        for k in ("telegram_bot_token", "webhook_url"):
            d[k] = "configurado" if d.get(k) else None
        return d
