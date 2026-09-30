"""Canales de notificación. Los secretos (tokens, URLs) se leen de variables de entorno.

- console: imprime la alerta.
- file: agrega la alerta a un archivo JSONL.
- telegram: requiere TB_TELEGRAM_BOT_TOKEN y TB_TELEGRAM_CHAT_ID. NO probado contra la API real
  desde el entorno de desarrollo (sin acceso de red); probado con un cliente HTTP simulado.
- webhook: POST JSON a TB_WEBHOOK_URL (mismo aviso).
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import requests

from ..config import Settings
from ..signals.alert import Alert
from ..timeutil import utcnow


class Notifier:
    name = "base"

    def send(self, alert: Alert) -> datetime:  # devuelve la hora de envío (UTC)
        raise NotImplementedError


class ConsoleNotifier(Notifier):
    name = "console"

    def __init__(self, verbose: bool = True):
        self.verbose = verbose

    def send(self, alert: Alert) -> datetime:
        print(alert.format_text() if self.verbose else alert.one_line(), flush=True)
        print("-" * 72, flush=True)
        return utcnow()


class FileNotifier(Notifier):
    name = "file"

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def send(self, alert: Alert) -> datetime:
        t = utcnow()
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"event": "notified", "channel": "file", "time": t.isoformat(),
                                 "alert": alert.to_dict()}, ensure_ascii=False) + "\n")
        return t


class TelegramNotifier(Notifier):
    name = "telegram"

    def __init__(self, token: str, chat_id: str, session=None):
        if not token or not chat_id:
            raise ValueError("Faltan TB_TELEGRAM_BOT_TOKEN o TB_TELEGRAM_CHAT_ID")
        self.url = f"https://api.telegram.org/bot{token}/sendMessage"
        self.chat_id = chat_id
        self.session = session or requests.Session()

    def send(self, alert: Alert) -> datetime:
        r = self.session.post(self.url, json={"chat_id": self.chat_id, "text": alert.format_text()}, timeout=10)
        r.raise_for_status()
        return utcnow()


class WebhookNotifier(Notifier):
    name = "webhook"

    def __init__(self, url: str, session=None):
        if not url:
            raise ValueError("Falta TB_WEBHOOK_URL")
        self.url = url
        self.session = session or requests.Session()

    def send(self, alert: Alert) -> datetime:
        r = self.session.post(self.url, json=alert.to_dict(), timeout=10)
        r.raise_for_status()
        return utcnow()


def build_notifiers(settings: Settings, runtime_dir: Path, verbose: bool = True) -> list[Notifier]:
    out: list[Notifier] = []
    for ch in settings.notify:
        if ch == "console":
            out.append(ConsoleNotifier(verbose))
        elif ch == "file":
            out.append(FileNotifier(Path(runtime_dir) / "notifications.jsonl"))
        elif ch == "telegram":
            out.append(TelegramNotifier(settings.telegram_bot_token, settings.telegram_chat_id))
        elif ch == "webhook":
            out.append(WebhookNotifier(settings.webhook_url))
        else:
            raise ValueError(f"Canal de notificación desconocido: {ch}")
    return out
