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


def test_bybit_closes_take_the_last_trade_of_each_minute(tmp_path, monkeypatch):
    import gzip

    csv = ("id,timestamp,price,volume,side,rpi\n"
           "1,1793491200292,100.0,0.1,buy,0\n2,1793491230000,101.5,0.1,sell,0\n3,1793491262000,99.0,0.1,buy,1\n")
    monkeypatch.setattr("tradingbot.data.http.get_bytes", lambda session, url, timeout=30: gzip.compress(csv.encode()))
    s = registro.bybit_closes(pd.Timestamp("2026-11-01", tz="UTC"), cache=tmp_path)
    assert list(s) == [101.5, 99.0]
    assert (tmp_path / "bybit" / "2026-11-01.parquet").exists()  # la segunda vez sale de la caché


def test_blitz_summary_is_sealed_and_counts_its_groups(tmp_path):
    (tmp_path / "blitz").mkdir()
    rows = [{"lado": "CALL", "p057": True, "horario_usuario": False, "resultado": "gana", "resultado_iq": "gana"},
            {"lado": "PUT", "p057": False, "horario_usuario": True, "resultado": "pierde", "resultado_iq": "pierde"}]
    (tmp_path / "blitz" / "2026-11-02.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    s = registro.resumen(tmp_path, now=pd.Timestamp("2026-11-04", tz="UTC"))
    assert s["blitz"]["todas"] == {"senales": 2} and s["blitz"]["p ≥ 0,57"] == {"senales": 1}
    assert s["blitz"]["horario del usuario"] == {"senales": 1}


def test_blitz_eth_is_in_the_daily_registry_and_summary(tmp_path, monkeypatch):
    calls = []
    for name in ("btc_day", "eth_day", "night_day", "blitz_day", "blitz_eth_day"):
        monkeypatch.setattr(registro, name, (lambda n: (lambda day: calls.append((n, day)) or []))(name))
    out = registro.run_day("2026-11-01", root=tmp_path, log=lambda *_: None)
    assert out["blitz_eth"] == 0 and ("blitz_eth_day", "2026-11-01") in calls
    assert (tmp_path / "blitz_eth" / "2026-11-01.jsonl").exists()
    r = registro.resumen(tmp_path, now=pd.Timestamp("2026-11-07", tz="UTC"))
    assert r["blitz_eth"]["dias"] == 1 and r["sellado_hasta"] == "2027-01-19"
