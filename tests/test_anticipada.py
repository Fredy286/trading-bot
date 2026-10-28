"""Modo de señales anticipadas (Estudio 16, H16b) para cuenta demo: decisión, diario y panel."""

import json
import threading
import urllib.request

import numpy as np
import pandas as pd
import pytest

from tradingbot.app.server import make_server
from tradingbot.data import synthetic
from tradingbot.data.clean import to_canonical
from tradingbot.live import anticipada
from tradingbot.research.calibration import Calibrator


class _Model:
    def __init__(self, p):
        self.p = p

    def predict_proba(self, X):
        return np.column_stack([1 - np.full(len(X), self.p), np.full(len(X), self.p)])


def _bundle(p=0.7):
    rng = np.random.default_rng(0)
    raw = rng.uniform(0, 1, 5000)
    cal = Calibrator().fit(raw, (rng.uniform(0, 1, 5000) < raw).astype(int))  # aprox. identidad
    feats = anticipada.FEATURES + ["p_ret", "p_clpos", "p_range", "p_r5", "p_r10", "p_r20", "p_tib10",
                                   "p_vol10", "p_n10"]
    return {"model": _Model(p), "calibrator": cal, "features": feats, "k": 50, "latencia": 10, "q": 0.05,
            "payout": 0.85, "ev_margin": 0.02, "model_id": "PRUEBA"}


@pytest.fixture(scope="module")
def bars():
    b, _ = to_canonical(synthetic.generate(start="2024-01-01", days=3, phi=0.0, seed=1))
    return b


def _sec(minute_open, n=50, seed=0):
    idx = pd.date_range(minute_open, periods=n, freq="s")
    c = 1.1 + np.cumsum(np.random.default_rng(seed).normal(0, 1e-5, n))
    return pd.DataFrame({"o": c, "h": c + 1e-6, "l": c - 1e-6, "c": c, "v": 1.0, "tb": 0.6, "n": 2.0}, index=idx)


def test_decide_signals_when_ev_clears_the_margin(bars):
    t = bars.index[-1] + pd.Timedelta(minutes=1)
    d = anticipada.decide(_bundle(0.7), bars, _sec(t), t)
    assert d["estado"] == "señal" and d["lado"] == 1 and d["ev"] > 0.02
    d2 = anticipada.decide(_bundle(0.51), bars, _sec(t), t)
    assert d2["estado"] == "sin señal"


def test_decide_refuses_stale_bars_and_ignores_seconds_after_k(bars):
    t = bars.index[-1] + pd.Timedelta(minutes=2)  # falta la vela anterior
    assert anticipada.decide(_bundle(), bars, _sec(t), t)["estado"] == "sin datos"
    t = bars.index[-1] + pd.Timedelta(minutes=1)
    s50, s60 = _sec(t, 50), _sec(t, 60)
    s60.iloc[50:, :4] += 1.0  # lo que pase desde el segundo 50 no cuenta
    assert anticipada.decide(_bundle(), bars, s50, t) == anticipada.decide(_bundle(), bars, s60, t)


def _jl(path, rows):
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


def test_diary_merges_click_binance_reference_and_platform(tmp_path):
    _jl(tmp_path / "senales.jsonl", [
        {"evento": "aviso", "alert_id": "a1", "decidido": "2026-11-01T12:00:50+00:00",
         "cierre": "2026-11-01T12:01:00+00:00", "lado": 1, "p": 0.6, "ev": 0.05},
        {"evento": "aviso", "alert_id": "a2", "decidido": "2026-11-01T12:05:50+00:00",
         "cierre": "2026-11-01T12:06:00+00:00", "lado": -1, "p": 0.58, "ev": 0.03},
        {"evento": "referencia", "alert_id": "a1", "entrada_binance": 100.0, "salida_binance": 101.0,
         "resultado_binance": 1}])
    _jl(tmp_path / "clics.jsonl", [{"alert_id": "a1", "hora_binance": "2026-11-01T12:00:57+00:00"},
                                   {"alert_id": "a1", "hora_binance": "2026-11-01T12:00:59+00:00"}])
    _jl(tmp_path / "registros.jsonl", [{"alert_id": "a1", "entrada": 100.1, "pago": 82},
                                       {"alert_id": "a1", "resultado": "gano", "salida": 101.2}])
    rows = anticipada.diario(tmp_path)
    a1 = next(r for r in rows if r["alert_id"] == "a1")
    assert a1["latencia_s"] == 7.0 and a1["coinciden"] is True and a1["pago"] == 82 and a1["salida_plataforma"] == 101.2
    r = anticipada.resumen(tmp_path)
    assert r["avisos"] == 2 and r["clics"] == 1 and r["acierto_binance"] == 1.0 and r["acierto_plataforma"] == 1.0
    assert r["ganancia_demo_por_unidad"] == pytest.approx(0.82) and r["coincidencia_binance_plataforma"] == 1.0


def test_binance_reference_uses_last_trade_before_click_and_plus_60s(tmp_path):
    _jl(tmp_path / "senales.jsonl", [{"evento": "aviso", "alert_id": "a1", "decidido": "2026-11-01T12:00:50+00:00",
                                      "cierre": "2026-11-01T12:01:00+00:00", "lado": -1, "p": 0.6, "ev": 0.05}])
    _jl(tmp_path / "clics.jsonl", [{"alert_id": "a1", "hora_binance": "2026-11-01T12:00:58.400000+00:00"}])

    class _Sec:
        def get(self, start, now, limit=120):
            idx = pd.date_range("2026-11-01T12:00:40", periods=100, freq="s", tz="UTC")
            c = 100.0 - 0.01 * np.arange(100)  # baja: la señal de venta acierta
            return pd.DataFrame({"o": c, "h": c, "l": c, "c": c, "v": 1.0, "tb": 0.5, "n": 1.0}, index=idx)

    class _Feed:
        offset_s, session = 0.0, None

    loop = anticipada.SignalLoop(_bundle(), tmp_path, feed=_Feed(), secfeed=_Sec(), sound=False)
    assert loop.fill_references(pd.Timestamp("2026-11-01T12:02:10", tz="UTC").to_pydatetime()) == 1
    ref = [r for r in map(json.loads, (tmp_path / "senales.jsonl").read_text().splitlines())
           if r.get("evento") == "referencia"][0]
    # Último precio antes de 12:00:58.4 = cierre de la vela 12:00:57 (índice 17); salida: la de 12:01:57 (77).
    assert ref["entrada_binance"] == pytest.approx(100 - 0.17) and ref["salida_binance"] == pytest.approx(100 - 0.77)
    assert ref["resultado_binance"] == 1 and ref["latencia_s"] == pytest.approx(8.4)
    assert loop.fill_references(pd.Timestamp("2026-11-01T12:03:00", tz="UTC").to_pydatetime()) == 0  # una vez


def _req(url, body=None):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def test_panel_records_click_once_and_validates_platform_data(tmp_path):
    sd = tmp_path / "senales"
    sd.mkdir()
    _jl(sd / "senales.jsonl", [{"evento": "aviso", "alert_id": "a1", "decidido": "2026-11-01T12:00:50+00:00",
                                "cierre": "2026-11-01T12:01:00+00:00", "lado": 1, "p": 0.6, "ev": 0.05}])
    (sd / "state.json").write_text(json.dumps({"desfase_reloj_s": 2.0, "ultimo": {}}), encoding="utf-8")
    srv = make_server("127.0.0.1", 0, tmp_path / "rt", tmp_path / "res", sd)
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    try:
        code, r1 = _req(base + "/api/senal/clic", {"alert_id": "a1"})
        assert code == 200 and pd.Timestamp(r1["hora_binance"]) - pd.Timestamp(r1["hora_pc"]) == pd.Timedelta(seconds=2)
        code, r2 = _req(base + "/api/senal/clic", {"alert_id": "a1"})
        assert r2.get("ya_registrado") and r2["hora_binance"] == r1["hora_binance"]
        assert _req(base + "/api/senal/clic", {"alert_id": "zz"})[0] == 404
        assert _req(base + "/api/senal/registro", {"alert_id": "a1", "resultado": "quizas"})[0] == 400
        assert _req(base + "/api/senal/registro", {"alert_id": "a1", "pago": 150})[0] == 400
        assert _req(base + "/api/senal/registro", {"alert_id": "a1", "resultado": "empate", "pago": "85"})[0] == 200
        code, st = _req(base + "/api/senal/state")
        assert code == 200 and st["diario"][0]["resultado_plataforma"] == 0 and st["resumen"]["clics"] == 1
        with urllib.request.urlopen(base + "/senales", timeout=5) as r:
            assert b"YA HICE CLIC" in r.read()
    finally:
        srv.shutdown()
        srv.server_close()


def test_quarter_turn_only_decides_in_the_minute_before_the_last_minute(bars, tmp_path):
    assert anticipada.quarter_turn(pd.Timestamp("2026-11-01 10:13", tz="UTC"), 1)
    assert not anticipada.quarter_turn(pd.Timestamp("2026-11-01 10:14", tz="UTC"), 1)

    class _Feed:
        offset_s, session = 0.0, None

        def server_now(self):
            return pd.Timestamp("2026-11-01 10:05:50", tz="UTC").to_pydatetime()

    loop = anticipada.SignalLoop(_bundle(), tmp_path, feed=_Feed(), secfeed=None, sound=False, cuarto_r=1, pago=0.87)
    d = loop.step(pd.Timestamp("2026-11-01 10:05:50.25", tz="UTC").to_pydatetime())
    assert d["estado"] == "fuera de turno" and d["proximo"].startswith("2026-11-01T10:13:50")


def test_real_payout_changes_the_expected_gain(bars):
    t = bars.index[-1] + pd.Timedelta(minutes=1)
    d85 = anticipada.decide(_bundle(0.56), bars, _sec(t), t)
    d87 = anticipada.decide(_bundle(0.56), bars, _sec(t), t, payout=0.87)
    assert d87["ev"] > d85["ev"]
