"""Grabador del libro de OKX dentro de las ventanas: turnos de las fotos, nombres de contrato y resultados."""

import json
from datetime import datetime, timedelta, timezone

import pandas as pd

from tradingbot.live import okx_eventos, okx_libro_dentro as od

U = timezone.utc


def test_photo_schedule_for_5_and_15_minute_windows():
    t = datetime(2026, 11, 11, 3, 7, 30, tzinfo=U)
    assert od.pendientes(t) == [(5, datetime(2026, 11, 11, 3, 5, tzinfo=U), 150)]
    assert od.pendientes(datetime(2026, 11, 11, 3, 8, 0, tzinfo=U)) == [(15, datetime(2026, 11, 11, 3, 0, tzinfo=U), 480)]
    assert od.pendientes(datetime(2026, 11, 11, 3, 9, 45, tzinfo=U)) == [(5, datetime(2026, 11, 11, 3, 5, tzinfo=U), 285)]
    assert od.pendientes(datetime(2026, 11, 11, 3, 14, 45, tzinfo=U)) == [
        (5, datetime(2026, 11, 11, 3, 10, tzinfo=U), 285), (15, datetime(2026, 11, 11, 3, 0, tzinfo=U), 885)]
    # inicio de una ventana de 5 min (lo graba el otro grabador); la de 15 min está en su segundo 600 (sin foto)
    assert od.pendientes(datetime(2026, 11, 11, 3, 10, 0, tzinfo=U)) == []
    assert od.pendientes(datetime(2026, 11, 11, 3, 10, 15, tzinfo=U)) == []


def test_instrument_names_match_the_live_module():
    ini = datetime(2026, 11, 7, 22, 45, tzinfo=U)
    assert od.inst_id("ETHUSDT", ini, 5) == okx_eventos.inst_id("ETHUSDT", pd.Timestamp(ini))
    assert od.inst_id("BTCUSDT", ini, 15) == okx_eventos.inst_id("BTCUSDT", pd.Timestamp(ini), 15)
    assert od.inst_id("SOLUSDT", ini, 15) == "SOL-UPDOWN-15MIN-261108-0645-0700"


class _Reloj:
    def __init__(self, t):
        self.t = t

    def ahora(self):
        return self.t

    def dormir(self, s):
        self.t += timedelta(seconds=s)


class _Resp:
    def __init__(self, j):
        self.j = j

    def raise_for_status(self):
        pass

    def json(self):
        return self.j


class _Sesion:
    def __init__(self, reloj):
        self.reloj = reloj

    def get(self, url, params=None, timeout=None):
        self.reloj.t += timedelta(seconds=0.05)
        if url.endswith("/index-tickers"):
            return _Resp({"code": "0", "data": [{"idxPx": "100.5"}]})
        if url.endswith("/books"):
            return _Resp({"code": "0", "data": [{"asks": [["0.7", "5", "0", "1"]], "bids": [["0.65", "3", "0", "1"]]}]})
        return _Resp({"code": "0", "data": [{"instId": f"{params['seriesId']}-X", "floorStrike": "100", "settleValue": "101",
                                             "outcome": "1", "expTime": "1"}]})


def test_records_photos_and_results_until_the_end(tmp_path):
    reloj = _Reloj(datetime(2026, 11, 11, 3, 4, 50, tzinfo=U))
    f = od.grabar(7 / 60, tmp_path, "github", session=_Sesion(reloj), ahora=reloj.ahora, dormir=reloj.dormir,
                  log=lambda *_: None)
    filas = [json.loads(x) for x in f.read_text().splitlines()]
    # de 03:04:50 a 03:11:50: 5 min → 60, 150, 240, 285 de la ventana 03:05 (4) y 60 de la 03:10 (1);
    # 15 min → 300, 480 y 660 de la ventana 03:00 (3); 3 monedas en cada foto
    assert len(filas) == 3 * (4 + 1 + 3)
    x = filas[0]
    assert x["fuente"] == "github" and x["indice"] == 100.5 and x["a"] == [[0.7, 5.0]] and x["b"] == [[0.65, 3.0]]
    assert {r["seg"] for r in filas if r["dur"] == 5 and r["inst"].endswith("1105-1110")} == set(od.FOTOS[5])
    res = [json.loads(x) for x in (tmp_path / (f.stem + "_resultados.jsonl")).read_text().splitlines()]
    assert len(res) == 6 and res[0]["resultado"] == "1"  # 3 monedas × 2 duraciones, sin repetir
