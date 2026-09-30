"""Guarda de seguridad para dinero real.

Por diseño, `assert_real_money_allowed` FALLA salvo que se cumplan TODAS estas condiciones:
  1. Variable de entorno TB_REAL_MONEY=AUTORIZO_OPERAR_CON_DINERO_REAL.
  2. Archivo de autorización firmado por el usuario (JSON) con: nombre, fecha, intermediario,
     instrumentos, monto máximo por operación, pérdida diaria máxima, fecha de caducidad y la frase
     exacta de consentimiento.
  3. El modelo tiene estado VALIDADO (desarrollo + periodo bloqueado + observación en vivo).
  4. La operación respeta los límites del archivo.
Además, en esta versión NO hay adaptador de intermediario real: aunque la guarda aprobara, no hay
código que envíe órdenes reales. Eso es intencional hasta completar la Fase 2.
"""

from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path

CONSENT_PHRASE = ("Autorizo expresamente operar con dinero real bajo los límites de este archivo y "
                  "entiendo que puedo perder todo el capital asignado.")
ENV_FLAG = "TB_REAL_MONEY"
ENV_VALUE = "AUTORIZO_OPERAR_CON_DINERO_REAL"
REQUIRED = ["authorized_by", "date", "broker", "instruments", "max_stake", "max_daily_loss", "expires",
            "consent"]


class RealMoneyBlocked(Exception):
    pass


def assert_real_money_allowed(auth_path: Path | None, model_status: str, instrument: str, stake: float,
                              today: date | None = None, env: dict | None = None) -> dict:
    env = os.environ if env is None else env
    today = today or date.today()
    if env.get(ENV_FLAG) != ENV_VALUE:
        raise RealMoneyBlocked(f"Dinero real deshabilitado: falta {ENV_FLAG}={ENV_VALUE}.")
    if auth_path is None or not Path(auth_path).exists():
        raise RealMoneyBlocked("Falta el archivo de autorización expresa del usuario.")
    auth = json.loads(Path(auth_path).read_text(encoding="utf-8"))
    missing = [k for k in REQUIRED if k not in auth]
    if missing:
        raise RealMoneyBlocked(f"Autorización incompleta; faltan: {missing}")
    if auth["consent"].strip() != CONSENT_PHRASE:
        raise RealMoneyBlocked("La frase de consentimiento no coincide exactamente.")
    if date.fromisoformat(auth["expires"]) < today:
        raise RealMoneyBlocked("La autorización caducó.")
    if model_status != "VALIDADO":
        raise RealMoneyBlocked(f"El modelo no está VALIDADO (estado: {model_status}).")
    if instrument not in auth["instruments"]:
        raise RealMoneyBlocked(f"{instrument} no está autorizado.")
    if stake > float(auth["max_stake"]):
        raise RealMoneyBlocked(f"Monto {stake} supera el máximo autorizado {auth['max_stake']}.")
    return auth
