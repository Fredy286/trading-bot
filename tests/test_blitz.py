"""Modo de práctica del blitz de BTC de IQ Option (Estudios 42 y 44): decisión, referencia con el compuesto y panel."""

import json
import threading
import urllib.request

import numpy as np
import pandas as pd
import pytest

from tradingbot.app.server import make_server
from tradingbot.data import synthetic
from tradingbot.data.clean import to_canonical
from tradingbot.live import blitz
from tradingbot.research.calibration import Calibrator
from tradingbot.research.study16 import PARTIAL
from tradingbot.research.study42 import COMP


class _Model:
    def __init__(self, p):
        self.p = p

    def predict_proba(self, X):
        return np.column_stack([1 - np.full(len(X), self.p), np.full(len(X), self.p)])


def _bundle(p=0.7):
    rng = np.random.default_rng(0)
    raw = rng.uniform(0, 1, 5000)
    cal = Calibrator().fit(raw, (rng.uniform(0, 1, 5000) < raw).astype(int))  # aprox. identidad
    return {"model": _Model(p), "calibrator": cal, "features": blitz.FEATURES + PARTIAL + COMP, "k": 50,
            "latencia": 10, "duracion_min": 3, "q": 0.0, "payout": 0.86, "ev_margin": 0.02, "model_id": "PRUEBA"}


@pytest.fixture(scope="module")
def bars():
    b, _ = to_canonical(synthetic.generate(start="2024-01-01", days=3, phi=0.0, seed=1))
    return b


def _sec(minute_open, n=50, seed=0):
    idx = pd.date_range(minute_open, periods=n, freq="s")
    c = 1.1 + np.cumsum(np.random.default_rng(seed).normal(0, 1e-5, n))
    return pd.DataFrame({"o": c, "h": c + 1e-6, "l": c - 1e-6, "c": c, "v": 1.0, "tb": 0.6, "n": 2.0}, index=idx)


def _venues(bars, t1, n=75):
    c = bars["c"][bars.index <= t1].iloc[-n:]
    return {"bybit": c * (1 - 1e-4), "okx": c * (1 + 5e-5)}


def test_decide_blitz_signals_with_the_86_payout_and_needs_every_venue(bars):
    t = bars.index[-1] + pd.Timedelta(minutes=1)
    t1 = bars.index[-1]
    d = blitz.decide_blitz(_bundle(0.7), bars, _sec(t), _venues(bars, t1), t)
    assert d["estado"] == "señal" and d["lado"] == 1
    assert d["ev"] == pytest.approx(0.7 * 0.86 - 0.3, abs=0.02)  # calibrador casi identidad
    assert d["compuesto"] == pytest.approx(bars["c"].iloc[-1] * (1 - 5e-5 / 3), rel=1e-9)
    assert blitz.decide_blitz(_bundle(0.54), bars, _sec(t), _venues(bars, t1), t)["estado"] == "sin señal"
    v = _venues(bars, t1)
    v["okx"] = v["okx"].iloc[:-1]  # falta el cierre anterior de OKX
    assert blitz.decide_blitz(_bundle(0.7), bars, _sec(t), v, t)["estado"] == "sin datos"


def test_decide_blitz_ignores_seconds_after_k(bars):
    t = bars.index[-1] + pd.Timedelta(minutes=1)
    v = _venues(bars, bars.index[-1])
    s50, s60 = _sec(t, 50), _sec(t, 60)
    s60.iloc[50:, :4] += 1.0
    assert blitz.decide_blitz(_bundle(), bars, s50, v, t) == blitz.decide_blitz(_bundle(), bars, s60, v, t)


def _jl(path, rows):
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


def test_reference_is_the_composite_from_the_alert_close_to_three_minutes_later(tmp_path):
    t = pd.Timestamp("2026-11-01T12:00", tz="UTC")
    _jl(tmp_path / "senales.jsonl", [{"evento": "aviso", "alert_id": "a1", "vela": t.isoformat(),
                                      "decidido": "2026-11-01T12:00:50+00:00", "cierre": "2026-11-01T12:01:00+00:00",
                                      "lado": -1, "p": 0.6, "ev": 0.05}])

    class _Venues:
        def get(self, venue, a, b):
            idx = pd.date_range(a, b, freq="min")
            base = {"binance": 100.0, "bybit": 99.0, "okx": 98.0}[venue]
            return pd.Series(base - np.arange(len(idx)), index=idx)  # baja: la venta acierta

    class _Feed:
        offset_s, session = 0.0, None

    loop = blitz.BlitzLoop(_bundle(), tmp_path, feed=_Feed(), secfeed=object(), venues=_Venues(), sound=False)
    assert loop.fill_references(pd.Timestamp("2026-11-01T12:04:10", tz="UTC").to_pydatetime()) == 0  # aún no
    assert loop.fill_references(pd.Timestamp("2026-11-01T12:04:30", tz="UTC").to_pydatetime()) == 1
    ref = [r for r in map(json.loads, (tmp_path / "senales.jsonl").read_text().splitlines())
           if r.get("evento") == "referencia"][0]
    assert ref["entrada_ref"] == pytest.approx(99.0) and ref["salida_ref"] == pytest.approx(96.0)
    assert ref["resultado_ref"] == 1
    assert loop.fill_references(pd.Timestamp("2026-11-01T12:06:00", tz="UTC").to_pydatetime()) == 0  # una vez


def test_usdt_closes_keep_only_confirmed_okx_candles():
    t1 = pd.Timestamp("2026-11-01T12:00", tz="UTC")
    ms = int(t1.timestamp() * 1000)

    class _Resp:
        def __init__(self, j):
            self.j = j

        def raise_for_status(self):
            pass

        def json(self):
            return self.j

    class _Session:
        def get(self, url, params, timeout):
            if "okx" in url:
                return _Resp({"data": [[str(ms + 60000), "1", "1", "1", "5.0", "0", "0", "0", "0"],
                                       [str(ms), "1", "1", "1", "4.0", "0", "0", "0", "1"]]})
            return _Resp({"result": {"list": [[str(ms), "1", "1", "1", "3.0", "0", "0"]]}})

    v = blitz.UsdtCloses(_Session()).recent(t1, n=2)
    assert list(v["okx"]) == [4.0] and list(v["bybit"]) == [3.0]


def _req(url, body=None):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def test_panel_serves_the_blitz_mode_from_its_own_folder(tmp_path):
    bd = tmp_path / "blitz"
    bd.mkdir()
    _jl(bd / "senales.jsonl", [
        {"evento": "aviso", "alert_id": "b1", "decidido": "2026-11-01T12:00:50+00:00",
         "cierre": "2026-11-01T12:01:00+00:00", "vence": "2026-11-01T12:04:00+00:00", "lado": 1, "p": 0.6, "ev": 0.1},
        {"evento": "referencia", "alert_id": "b1", "entrada_ref": 1.0, "salida_ref": 2.0, "resultado_ref": 1}])
    (bd / "state.json").write_text(json.dumps({"desfase_reloj_s": 0.0, "ultimo": {}, "modo": "blitz"}), encoding="utf-8")
    srv = make_server("127.0.0.1", 0, tmp_path / "rt", tmp_path / "res", tmp_path / "senales", blitz_dir=bd)
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    try:
        assert _req(base + "/api/blitz/clic", {"alert_id": "b1"})[0] == 200
        assert (bd / "clics.jsonl").exists() and not (tmp_path / "senales" / "clics.jsonl").exists()
        assert _req(base + "/api/blitz/registro", {"alert_id": "b1", "resultado": "gano"})[0] == 200
        code, st = _req(base + "/api/blitz/state")
        f = st["diario"][0]
        assert code == 200 and st["modo"] == "blitz" and f["resultado_ref"] == 1 and f["coinciden"] is True
        assert st["resumen"]["acierto_ref"] == 1.0 and st["resumen"]["ganancia_demo_por_unidad"] == pytest.approx(0.86)
        with urllib.request.urlopen(base + "/blitz", timeout=5) as r:
            html = r.read()
            assert b"YA HICE CLIC" in html and b"/api/blitz" in html
    finally:
        srv.shutdown()
        srv.server_close()
