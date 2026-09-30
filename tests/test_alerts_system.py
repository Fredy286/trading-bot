"""Pruebas del sistema de alertas: formato, motor, monitor, notificadores, guarda y panel."""

import json
import threading
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from tradingbot.config import Settings
from tradingbot.data import synthetic
from tradingbot.data.clean import to_canonical
from tradingbot.execution.guard import CONSENT_PHRASE, ENV_FLAG, ENV_VALUE, RealMoneyBlocked, assert_real_money_allowed
from tradingbot.instruments import get_instrument
from tradingbot.live.feeds import BinancePollingFeed, ReplayFeed
from tradingbot.live.runner import AlertLoop
from tradingbot.notify import TelegramNotifier, WebhookNotifier, build_notifiers
from tradingbot.signals.alert import EXPERIMENTAL, NO_SIGNAL, PAUSED, SIGNAL, Alert, fictitious_example
from tradingbot.signals.engine import RiskState, SignalEngine
from tradingbot.signals.monitor import evaluate_monitor
from tradingbot.signals.registry import fit_bundle, validation_status_for


@pytest.fixture(scope="module")
def bars_edge():
    raw = synthetic.generate(start="2023-01-02", days=40, phi=-0.3, seed=21)
    return to_canonical(raw)[0]


@pytest.fixture(scope="module")
def bundle_edge(bars_edge):
    b = fit_bundle(bars_edge[bars_edge.index < pd.Timestamp("2023-02-01", tz="UTC")], "SYNTH", 1, "logit",
                   "synthetic", 1e-5, synthetic=True)
    return b


def _engine(bundle, **kw):
    s = Settings(instruments=["SYNTH"], max_alerts_per_day=10_000, max_daily_loss=1e9,
                 max_consecutive_losses=10_000, **kw)
    return SignalEngine(bundle, s, get_instrument("SYNTH"), price_source="SINTÉTICO"), s


def test_fictitious_example_format():
    ex = fictitious_example()
    assert ex.startswith("EJEMPLO FICTICIO — EUR/USD | 15:00 America/Bogota")
    assert "probabilidad: no calculada" in ex and "pago: no verificado" in ex and "estado: NO OPERAR" in ex


def test_alert_roundtrip_and_bogota_time():
    t = datetime(2024, 3, 1, 20, 0, tzinfo=timezone.utc)
    a = Alert(instrument="EUR/USD", status=NO_SIGNAL, price_source="x", broker="y", decision_time=t, duration_min=1)
    d = a.to_dict()
    assert d["decision_time_bogota"] == "2024-03-01 15:00:00 America/Bogota"  # UTC−5
    b = Alert.from_dict(json.loads(json.dumps(d)))
    assert b.decision_time == t and b.alert_id == a.alert_id
    assert "15:00 America/Bogota" in a.one_line() and "SIN SEÑAL" in a.one_line()


def test_unvalidated_model_never_emits_actionable_signal(bars_edge, bundle_edge):
    eng, s = _engine(bundle_edge, show_experimental=False)
    feed = ReplayFeed(bars_edge)
    statuses = set()
    for i in range(120):
        now = (pd.Timestamp("2023-02-06 13:00", tz="UTC") + pd.Timedelta(minutes=i, seconds=3)).to_pydatetime()
        a = eng.evaluate(feed.get(now)[0], now, RiskState())
        statuses.add(a.status)
        assert a.status != SIGNAL
        if a.status == NO_SIGNAL:
            assert a.direction is None and a.no_signal_reason
    assert statuses == {NO_SIGNAL}


def test_experimental_alert_has_all_required_fields(bars_edge, bundle_edge):
    eng, s = _engine(bundle_edge, show_experimental=True)
    feed = ReplayFeed(bars_edge)
    found = None
    for i in range(240):
        now = (pd.Timestamp("2023-02-06 13:00", tz="UTC") + pd.Timedelta(minutes=i, seconds=3)).to_pydatetime()
        a = eng.evaluate(feed.get(now)[0], now, RiskState())
        if a.status == EXPERIMENTAL:
            found = a
            break
    assert found is not None
    a = found
    assert a.instrument and a.broker and a.price_source and a.decision_time and a.act_before
    assert a.direction in ("sube", "baja") and a.duration_min == 1
    assert a.prob_lo <= a.prob <= a.prob_hi and a.prob_n > 0
    assert a.payout == 0.85 and a.payout_verified is False and a.costs and a.ev >= s.ev_margin
    assert a.prob_lo > a.breakeven
    assert len(a.reasons) >= 3 and len(a.invalidators) >= 3
    assert (a.act_before - a.decision_time).total_seconds() == 20


def test_stale_data_and_risk_limits_block(bars_edge, bundle_edge):
    eng, s = _engine(bundle_edge, show_experimental=True)
    feed = ReplayFeed(bars_edge)
    now = pd.Timestamp("2023-02-06 13:00:03", tz="UTC").to_pydatetime()
    bars = feed.get(now)[0]
    late = now + pd.Timedelta(minutes=10)
    assert "desactualizados" in eng.evaluate(bars, late, RiskState()).no_signal_reason
    s.max_consecutive_losses = 2
    r = RiskState(consecutive_losses=2)
    a = eng.evaluate(bars, now, r)
    assert a.status == NO_SIGNAL
    paused = eng.evaluate(bars, now, RiskState(), monitor_status="PAUSADO")
    assert paused.status == PAUSED


def test_monitor_pauses_on_deterioration_and_flags_overconfidence():
    good = [{"win": i % 10 < 6, "tie": False, "prob": 0.6} for i in range(200)]
    assert evaluate_monitor(good, 0.5405).status == "OK"
    bad = [{"win": i % 10 < 4, "tie": False, "prob": 0.6} for i in range(200)]
    assert evaluate_monitor(bad, 0.5405).status == "PAUSADO"
    few = [{"win": False, "tie": False, "prob": 0.6}] * 10
    assert evaluate_monitor(few, 0.5405).status == "OK"  # aún no hay muestra para juzgar
    over = [{"win": i % 100 < 58, "tie": False, "prob": 0.70} for i in range(1000)]
    assert evaluate_monitor(over, 0.5405).status == "EXPERIMENTAL"


def test_validation_status_derived_from_files(tmp_path):
    fz = tmp_path / "frozen.json"
    assert validation_status_for("EURUSD", 1, "logit", fz)[0] == "NO_VALIDADO"
    fz.write_text(json.dumps({"verdict": "SIN SEÑAL", "candidates": []}))
    assert validation_status_for("EURUSD", 1, "logit", fz)[0] == "NO_VALIDADO"
    fz.write_text(json.dumps({"verdict": "x", "candidates": [{"symbol": "EURUSD", "horizon": 1, "model": "logit"}]}))
    assert validation_status_for("EURUSD", 1, "logit", fz)[0] == "CANDIDATO_DEV"
    hv = tmp_path / "holdout.json"
    hv.write_text(json.dumps({"passed": [{"symbol": "EURUSD", "horizon": 1, "model": "logit"}]}))
    lv = tmp_path / "live.json"
    lv.write_text(json.dumps({"passed": True, "symbol": "EURUSD", "model": "logit"}))
    assert validation_status_for("EURUSD", 1, "logit", fz, hv)[0] == "VALIDADO_HOLDOUT"
    assert validation_status_for("EURUSD", 1, "logit", fz, hv, lv)[0] == "VALIDADO"


def _auth(tmp_path, **over):
    d = {"authorized_by": "usuario", "date": "2026-09-30", "broker": "demo", "instruments": ["EURUSD"],
         "max_stake": 1, "max_daily_loss": 5, "expires": "2026-12-31", "consent": CONSENT_PHRASE}
    d.update(over)
    p = tmp_path / "auth.json"
    p.write_text(json.dumps(d))
    return p


def test_real_money_guard_blocks_by_default(tmp_path):
    env_ok = {ENV_FLAG: ENV_VALUE}
    with pytest.raises(RealMoneyBlocked):
        assert_real_money_allowed(None, "VALIDADO", "EURUSD", 1, env={})
    with pytest.raises(RealMoneyBlocked):
        assert_real_money_allowed(None, "VALIDADO", "EURUSD", 1, env=env_ok)
    with pytest.raises(RealMoneyBlocked):
        assert_real_money_allowed(_auth(tmp_path), "CANDIDATO_DEV", "EURUSD", 1, today=date(2026, 10, 1), env=env_ok)
    with pytest.raises(RealMoneyBlocked):
        assert_real_money_allowed(_auth(tmp_path, consent="sí"), "VALIDADO", "EURUSD", 1, today=date(2026, 10, 1),
                                  env=env_ok)
    with pytest.raises(RealMoneyBlocked):
        assert_real_money_allowed(_auth(tmp_path), "VALIDADO", "EURUSD", 2, today=date(2026, 10, 1), env=env_ok)
    with pytest.raises(RealMoneyBlocked):
        assert_real_money_allowed(_auth(tmp_path), "VALIDADO", "EURUSD", 1, today=date(2027, 1, 1), env=env_ok)
    ok = assert_real_money_allowed(_auth(tmp_path), "VALIDADO", "EURUSD", 1, today=date(2026, 10, 1), env=env_ok)
    assert ok["max_stake"] == 1


def test_settings_from_env_and_no_secret_leak():
    s = Settings.from_env({"TB_INSTRUMENTS": "eurusd, btcusdt", "TB_PAYOUT": "0.8", "TB_HOURS_BOGOTA": "7-16",
                           "TB_TELEGRAM_BOT_TOKEN": "123:SECRETO", "TB_NOTIFY": "console,telegram"})
    assert s.instruments == ["EURUSD", "BTCUSDT"] and s.payout == 0.8 and s.allowed_hours_bogota == (7, 16)
    assert "SECRETO" not in json.dumps(s.public_dict())
    with pytest.raises(ValueError):
        Settings.from_env({"TB_CONTRACT": "futuros"})
    with pytest.raises(ValueError):
        build_notifiers(Settings(notify=["telegram"]), Path("/tmp"))  # faltan credenciales


class _FakeSession:
    def __init__(self):
        self.calls = []

    def post(self, url, json=None, timeout=None):
        self.calls.append((url, json))

        class R:
            def raise_for_status(self):
                pass
        return R()


def test_telegram_and_webhook_payloads():
    a = Alert(instrument="EUR/USD", status=NO_SIGNAL, price_source="x", broker="y",
              decision_time=datetime(2024, 1, 1, tzinfo=timezone.utc), duration_min=1)
    fs = _FakeSession()
    TelegramNotifier("TOKEN", "42", session=fs).send(a)
    assert fs.calls[0][0].endswith("/botTOKEN/sendMessage") and fs.calls[0][1]["chat_id"] == "42"
    fs2 = _FakeSession()
    WebhookNotifier("https://ejemplo.invalid/hook", session=fs2).send(a)
    assert fs2.calls[0][1]["alert_id"] == a.alert_id


def test_binance_live_parse_drops_open_candle():
    t0 = int(pd.Timestamp("2026-01-01 10:00", tz="UTC").timestamp() * 1000)
    payload = [[t0 + 60000 * i, "100", "101", "99", "100.5", "2", t0 + 60000 * i + 59999, "0", 5, "0", "0", "0"]
               for i in range(3)]
    now = datetime.fromtimestamp((t0 + 60000 * 2 + 30000) / 1000, tz=timezone.utc)  # la 3.ª vela sigue abierta
    bars = BinancePollingFeed.parse(payload, now)
    assert len(bars) == 2 and bars.index[-1] == pd.Timestamp("2026-01-01 10:01", tz="UTC")


def test_alert_loop_records_lifecycle(tmp_path, bars_edge, bundle_edge):
    eng, s = _engine(bundle_edge, show_experimental=True)
    loop = AlertLoop(eng, ReplayFeed(bars_edge), [], tmp_path, s)
    for i in range(60):
        loop.step((pd.Timestamp("2023-02-06 13:00", tz="UTC") + pd.Timedelta(minutes=i, seconds=3)).to_pydatetime())
    events = [json.loads(l) for l in open(tmp_path / "events.jsonl")]
    kinds = {e["event"] for e in events}
    assert {"generated", "evaluated"} <= kinds
    ev = [e for e in events if e["event"] == "evaluated"]
    assert all(e["outcome"]["resultado"] in ("acierto", "fallo", "empate", "no_evaluable") for e in ev)
    state = json.loads((tmp_path / "state.json").read_text())
    assert state["model"]["validation_status"] == "NO_VALIDADO" and state["alerts"]
    assert sum(state["counts"].values()) == 60


def test_dashboard_server_endpoints(tmp_path, bars_edge, bundle_edge):
    from tradingbot.app.server import make_server

    eng, s = _engine(bundle_edge, show_experimental=True)
    loop = AlertLoop(eng, ReplayFeed(bars_edge), [], tmp_path, s)
    for i in range(30):
        loop.step((pd.Timestamp("2023-02-06 13:00", tz="UTC") + pd.Timedelta(minutes=i, seconds=3)).to_pydatetime())
    srv = make_server("127.0.0.1", 0, tmp_path, tmp_path / "results")
    port = srv.server_address[1]
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    try:
        base = f"http://127.0.0.1:{port}"
        html = urllib.request.urlopen(base + "/").read().decode()
        assert "Investigación y alertas" in html
        st = json.loads(urllib.request.urlopen(base + "/api/state").read())
        aid = st["alerts"][0]["alert_id"]
        req = urllib.request.Request(base + "/api/ack", data=json.dumps({"alert_id": aid}).encode(),
                                     headers={"Content-Type": "application/json"}, method="POST")
        assert json.loads(urllib.request.urlopen(req).read())["ok"]
        st = json.loads(urllib.request.urlopen(base + "/api/state").read())
        assert st["alerts"][0]["received_at"]
        bad = urllib.request.Request(base + "/api/ack", data=b"{}", method="POST")
        with pytest.raises(urllib.error.HTTPError):
            urllib.request.urlopen(bad)
    finally:
        srv.shutdown()
        srv.server_close()


def test_live_verdict_requires_sample_and_edge():
    from tradingbot.signals.monitor import live_verdict

    few = [{"win": True, "tie": False, "pnl": 0.85}] * 50
    assert not live_verdict(few, 0.5405, "EURUSD", "logit")["passed"]  # muestra insuficiente
    coin = [{"win": i % 2 == 0, "tie": False, "pnl": 0.85 if i % 2 == 0 else -1.0} for i in range(400)]
    v = live_verdict(coin, 0.5405, "EURUSD", "logit")
    assert not v["passed"] and v["reasons"]
    good = [{"win": i % 10 < 7, "tie": False, "pnl": 0.85 if i % 10 < 7 else -1.0} for i in range(400)]
    assert live_verdict(good, 0.5405, "EURUSD", "logit")["passed"]
