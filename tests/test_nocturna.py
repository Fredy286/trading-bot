"""Modo de reversión nocturna: banda, ventana, aviso y resultado de referencia con un proveedor simulado."""

import numpy as np
import pandas as pd

from tradingbot.live import nocturna


def test_band_side_and_window():
    flat = np.r_[np.full(19, 1.0) + np.random.default_rng(0).normal(0, 1e-4, 19), 0.99]
    assert nocturna.band_side(flat) == 1  # cierre bajo la banda inferior → CALL
    assert nocturna.band_side(2 - flat) == -1
    assert nocturna.band_side(np.full(20, 1.0)) == 0
    jul, ene = pd.Timestamp("2026-07-01 21:05", tz="UTC"), pd.Timestamp("2026-01-15 21:05", tz="UTC")
    assert nocturna.in_window(jul, "utc") and nocturna.in_window(ene, "utc")
    assert nocturna.in_window(jul, "nueva_york") and not nocturna.in_window(ene, "nueva_york")


class FakeFeed:
    offset_s = 0.0

    def __init__(self, t0):
        self.t0 = t0
        closes = np.r_[np.full(20, 1.0) + np.random.default_rng(1).normal(0, 1e-4, 20), 0.99]
        self.c = pd.DataFrame({"open": closes, "high": closes, "low": closes, "close": closes},
                              index=t0 - 60 * np.arange(21, 0, -1))  # 21 velas cerradas, la última en t0 − 60
        self.clock = t0 + 2

    def now(self):
        return self.clock

    def sync_clock(self):
        return 0.0

    def candles(self, pair, count=22):
        return self.c

    def ticks(self, pair, start, end):
        t = np.arange(self.t0, self.t0 + 400, 1.0)
        return t, 1.0 + (t - self.t0) * 1e-6  # el precio sube: la CALL gana


def test_step_emits_call_and_resolve_measures_it(tmp_path):
    t0 = int(pd.Timestamp("2026-07-01 21:10", tz="UTC").timestamp())
    feed = FakeFeed(t0)
    loop = nocturna.NightLoop(tmp_path, feed=feed, ventana="utc", pairs=("EURGBP",), sound=False, log=lambda *_: None)
    out = loop.step(t0)
    assert len(out) == 1 and out[0]["lado"] == "CALL"
    assert loop.step(t0 + 60) == []  # el par queda ocupado 3 min
    loop.resolve(t0 + 100)
    assert loop.pending  # aún no vence
    loop.resolve(t0 + 10 + 180 + 20)
    d = nocturna.diario(tmp_path)
    assert d[0]["resultado"] == "gana" and d[0]["demora_s"] == 10
    assert nocturna.resumen(tmp_path)["acierto"] == 1.0


def test_outside_window_does_nothing(tmp_path):
    t0 = int(pd.Timestamp("2026-07-01 15:10", tz="UTC").timestamp())
    loop = nocturna.NightLoop(tmp_path, feed=FakeFeed(t0), ventana="utc", pairs=("EURGBP",), sound=False,
                              log=lambda *_: None)
    assert loop.step(t0) == [] and loop.last["estado"] == "fuera de ventana"


def test_panel_routes(tmp_path):
    import json
    import threading
    import urllib.error
    import urllib.request

    from tradingbot.app.server import make_server

    nd = tmp_path / "noc"
    nd.mkdir()
    (nd / "senales.jsonl").write_text(json.dumps({"evento": "aviso", "alert_id": "n1", "par": "EURGBP", "lado": "PUT",
                                                  "entrada_desde": "2026-07-01T21:10:00+00:00"}) + "\n", encoding="utf-8")
    (nd / "state.json").write_text(json.dumps({"desfase_reloj_s": -1.5, "ventana": "utc", "ultimo": {}}), encoding="utf-8")
    srv = make_server("127.0.0.1", 0, tmp_path / "rt", tmp_path / "res", tmp_path / "sen", nd)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"

    def req(url, body=None):
        data = None if body is None else json.dumps(body).encode()
        r = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(r, timeout=5) as resp:
                return resp.status, json.loads(resp.read())
        except urllib.error.HTTPError as e:
            return e.code, {}

    try:
        code, r1 = req(base + "/api/nocturna/clic", {"alert_id": "n1"})
        assert code == 200 and pd.Timestamp(r1["hora_pc"]) - pd.Timestamp(r1["hora_deriv"]) == pd.Timedelta(seconds=1.5)
        assert req(base + "/api/nocturna/clic", {"alert_id": "n1"})[1].get("ya_registrado")
        assert req(base + "/api/nocturna/clic", {"alert_id": "zz"})[0] == 404
        code, st = req(base + "/api/nocturna/state")
        assert code == 200 and st["diario"][0]["clic"] == r1["hora_deriv"] and st["resumen"]["avisos"] == 1
        with urllib.request.urlopen(base + "/nocturna", timeout=5) as r:
            assert "Ya entré" in r.read().decode()
    finally:
        srv.shutdown()
