"""Grabador del libro de OKX (Estudio 56): nombres de contrato, turnos de las fotos y archivo."""

import json
from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest
import requests

from tradingbot.live import okx_eventos, okx_libro as ol


@pytest.mark.parametrize("t", ["2026-11-07 22:50", "2026-11-07 15:55", "2026-12-31 23:55", "2027-02-28 16:00"])
def test_instrument_name_matches_the_live_mode(t):
    ts = pd.Timestamp(t, tz="UTC")
    for s in ol.SERIES:
        assert ol.inst_id(s, ts.to_pydatetime()) == okx_eventos.inst_id(s, ts)


def test_next_window_starts_on_a_multiple_of_five_minutes():
    u = timezone.utc
    assert ol.proxima_ventana(datetime(2026, 11, 9, 0, 4, 50, tzinfo=u)) == datetime(2026, 11, 9, 0, 5, tzinfo=u)
    assert ol.proxima_ventana(datetime(2026, 11, 9, 0, 5, tzinfo=u)) == datetime(2026, 11, 9, 0, 5, tzinfo=u)
    assert ol.proxima_ventana(datetime(2026, 11, 9, 0, 5, 0, 1000, tzinfo=u)) == datetime(2026, 11, 9, 0, 10, tzinfo=u)
    assert ol.proxima_ventana(datetime(2026, 11, 9, 23, 57, tzinfo=u)) == datetime(2026, 11, 10, 0, 0, tzinfo=u)


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
    """API falsa: cada consulta tarda 0,1 s; el BTC de la 2.ª ventana no existe y el ETH de la 3.ª no responde."""

    def __init__(self, reloj):
        self.reloj, self.pedidos = reloj, []

    def get(self, url, params=None, timeout=None):
        if url.endswith("/public/time"):
            return _Resp({"code": "0", "data": [{"ts": str(int(self.reloj.t.timestamp() * 1000) + 250)}]})
        self.reloj.t += timedelta(seconds=0.1)
        self.pedidos.append((params["instId"], self.reloj.t))
        if params["instId"].startswith("BTC") and params["instId"].endswith("0820"):
            return _Resp({"code": "51001", "msg": "Instrument ID does not exist", "data": []})
        if params["instId"].startswith("ETH") and params["instId"].endswith("0825"):
            raise requests.ConnectionError("sin red")
        return _Resp({"code": "0", "data": [{"asks": [["0.52", "13.1", "0", "1"], ["0.55", "8.2", "0", "1"]],
                                             "bids": [["0.48", "13.1", "0", "3"]], "ts": "1"}]})


def test_records_four_photos_per_window_and_stops_in_time(tmp_path):
    reloj = _Reloj(datetime(2026, 11, 9, 0, 4, 52, tzinfo=timezone.utc))  # muy tarde para la ventana de las 00:05
    ses = _Sesion(reloj)
    archivo = ol.grabar(16 / 60, tmp_path, "github", session=ses, ahora=reloj.ahora, dormir=reloj.dormir,
                        log=lambda *_: None)
    filas = [json.loads(x) for x in archivo.read_text(encoding="utf-8").splitlines()]
    # hora de OKX = local + 0,25 s; empieza 00:04:52,25 y termina 00:20:52,25: ventanas 00:10, 00:15 y 00:20
    assert [f["ventana"] for f in filas] == ["2026-11-09T00:10:00.000Z", "2026-11-09T00:15:00.000Z",
                                             "2026-11-09T00:20:00.000Z"]
    assert archivo.name == "2026-11-09_0004.jsonl"
    f0 = filas[0]
    assert f0["fuente"] == "github" and f0["ETHUSDT"]["inst"] == "ETH-UPDOWN-5MIN-261109-0810-0815"
    assert [x["seg"] for x in f0["ETHUSDT"]["fotos"]] == list(ol.FOTOS_S)
    assert f0["ETHUSDT"]["fotos"][0]["a"] == [[0.52, 13.1], [0.55, 8.2]] and f0["ETHUSDT"]["fotos"][0]["b"] == [[0.48, 13.1]]
    # cada foto se toma en su segundo (hora de OKX), no antes
    for x in f0["ETHUSDT"]["fotos"]:
        t = pd.Timestamp(x["t"])
        assert pd.Timestamp("2026-11-09 00:10", tz="UTC") + pd.Timedelta(seconds=x["seg"]) <= t
        assert t - (pd.Timestamp("2026-11-09 00:10", tz="UTC") + pd.Timedelta(seconds=x["seg"])) < pd.Timedelta(seconds=1)
    # los fallos quedan anotados en la foto, sin detener la grabación
    assert all(x["error"].startswith("51001") for x in filas[1]["BTCUSDT"]["fotos"])
    assert all(x["error"].startswith("ConnectionError") for x in filas[2]["ETHUSDT"]["fotos"])
    assert "a" in filas[2]["BTCUSDT"]["fotos"][0]
