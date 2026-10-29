"""Registro diario: la reversión nocturna con un proveedor simulado y el sello de los aciertos."""

import json

import numpy as np
import pandas as pd

from tradingbot.live import registro


class FakeDeriv:
    def __init__(self, day):
        self.w0 = int(pd.Timestamp(day + " 21:00", tz="UTC").timestamp())

    def _call(self, req):
        ep = np.arange(self.w0 - 3600, self.w0 + 3 * 3600, 60)
        close = 1.0 + 1e-4 * np.sin(np.arange(len(ep)) / 3.0)
        close[(ep - self.w0) // 60 == 29] = 0.99  # la vela de las 21:29 se desploma → CALL a las 21:30
        return {"candles": [{"epoch": int(e), "close": float(c)} for e, c in zip(ep, close)]}

    def ticks(self, pair, start, end):
        t = np.arange(start, end, 1.0)
        return t, 1.0 + (t - start) * 1e-7


def test_night_day_registers_and_resolves():
    rows = registro.night_day("2026-07-01", feed=FakeDeriv("2026-07-01"), pairs=("EURGBP",))
    call = [r for r in rows if r["vela"] == "2026-07-01T21:30:00+00:00" and r["variante"] == "actual"]
    assert call and call[0]["lado"] == "CALL" and call[0]["resultado"] == "gana"
    assert all(r["resultado"] is not None for r in rows)


def test_summary_is_sealed_until_the_confirmation_date(tmp_path):
    (tmp_path / "btc").mkdir()
    (tmp_path / "btc" / "2026-10-27.jsonl").write_text(
        json.dumps({"lado": "CALL", "umbral_060": True, "cuarto_hora": False, "resultado": "gana"}) + "\n",
        encoding="utf-8")
    s = registro.resumen(tmp_path, now=pd.Timestamp("2026-11-01", tz="UTC"))
    assert s["sellado_hasta"] == "2027-01-19" and "acierto" not in s["btc"]["todas"]
    o = registro.resumen(tmp_path, abrir=True, now=pd.Timestamp("2026-11-01", tz="UTC"))
    assert o["btc"]["todas"]["acierto"] == 1.0 and (tmp_path / "aperturas_del_sello.log").exists()
    assert registro.resumen(tmp_path, now=pd.Timestamp("2027-02-01", tz="UTC"))["btc"]["p ≥ 0,60"]["acierto"] == 1.0
