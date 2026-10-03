"""Pruebas del sistema de alertas: formato, motor, monitor, notificadores, guarda y panel."""

import copy
import json
import os
import threading
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from tradingbot import jsonutil
from tradingbot.config import Settings
from tradingbot.data import synthetic
from tradingbot.data.clean import to_canonical
from tradingbot.execution.guard import CONSENT_PHRASE, ENV_FLAG, ENV_VALUE, RealMoneyBlocked, assert_real_money_allowed
from tradingbot.instruments import get_instrument
from tradingbot.execution.paper import PaperLedger, read_rows
from tradingbot.live.feeds import BinancePollingFeed, ReplayFeed
from tradingbot.live.runner import EARLY_TOLERANCE_S, LIVE_METHOD, AlertLoop, RuntimeLock
from tradingbot.notify import TelegramNotifier, WebhookNotifier, build_notifiers
from tradingbot.signals.alert import EXPERIMENTAL, NO_SIGNAL, PAUSED, SIGNAL, Alert, fictitious_example
from tradingbot.signals.engine import RiskState, SignalEngine
from tradingbot.signals.monitor import LIVE_SAMPLE_N, evaluate_monitor
from tradingbot.signals.registry import apply_policy, fit_bundle, policy_of, validation_status_for


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


POL = policy_of(Settings())  # política con la que corren las pruebas (la de _engine)


def _register(tmp_path, model_id, symbol="SYNTH", policy=None):
    """Registro de observación (como config/observacion_en_vivo.json) para las pruebas."""
    p = tmp_path / "observacion.json"
    p.write_text(json.dumps({"symbol": symbol, "horizon": 1, "model": "logit", "model_id": model_id,
                             "policy": policy or POL, "sample_n": LIVE_SAMPLE_N, "max_days": 56}), encoding="utf-8")
    return p


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
    # El IC90 es del acierto histórico del grupo de confianza parecida, no de `prob` (que puede quedar fuera).
    assert a.prob_lo <= a.prob_bin_hit <= a.prob_hi and a.prob_n > 0
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
    reg = _register(tmp_path, "M1", symbol="EURUSD")
    ok = {"passed": True, "symbol": "EURUSD", "model": "logit", "horizon": 1, "muestra_fija": True,
          "min_n": LIVE_SAMPLE_N, "breakeven": 1 / 1.85, "payout": 0.85, "model_id": "M1", "policy": POL}
    lv.write_text(json.dumps({**ok, "horizon": 5}))
    assert validation_status_for("EURUSD", 1, "logit", fz, hv, observation_path=reg)[0] == "VALIDADO_HOLDOUT"
    # Un veredicto en vivo de otro horizonte no valida este modelo.
    assert validation_status_for("EURUSD", 1, "logit", fz, hv, lv, reg)[0] == "VALIDADO_HOLDOUT"
    # Criterios relajados, otro entrenamiento u otra política (p. ej. pago 0,92 del .env) tampoco validan.
    for relaxed in ({"min_n": 30}, {"breakeven": 0.30}, {"muestra_fija": False}, {"model_id": "otro"},
                    {"policy": {**POL, "payout": 0.92}, "payout": 0.92, "breakeven": 1 / 1.92}):
        lv.write_text(json.dumps({**ok, **relaxed}))
        assert validation_status_for("EURUSD", 1, "logit", fz, hv, lv, reg)[0] == "VALIDADO_HOLDOUT"
    lv.write_text(json.dumps(ok))
    assert validation_status_for("EURUSD", 1, "logit", fz, hv, lv, tmp_path / "sin_registro.json")[0] == \
        "VALIDADO_HOLDOUT"  # sin observación registrada no hay VALIDADO
    assert validation_status_for("EURUSD", 1, "logit", fz, hv, lv, reg)[0] == "VALIDADO"


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
    assert not live_verdict(few, 0.5405, "EURUSD", "logit", min_n=200)["passed"]  # muestra insuficiente
    coin = [{"win": i % 2 == 0, "tie": False, "pnl": 0.85 if i % 2 == 0 else -1.0} for i in range(400)]
    v = live_verdict(coin, 0.5405, "EURUSD", "logit", min_n=200)
    assert not v["passed"] and v["reasons"]
    good = [{"win": i % 10 < 7, "tie": False, "pnl": 0.85 if i % 10 < 7 else -1.0} for i in range(400)]
    assert live_verdict(good, 0.5405, "EURUSD", "logit", min_n=200)["passed"]
    assert not live_verdict(good, 0.5405, "EURUSD", "logit")["passed"]  # por defecto: muestra fija de 3 500


class _LivePriceFeed(ReplayFeed):
    """Fuente simulada con precio «en vivo» = cierre de la última vela + desplazamiento conocido."""

    def __init__(self, bars, drift):
        super().__init__(bars)
        self.drift = drift

    def current_price(self, now_utc):
        b, _ = self.get(now_utc)
        return float(b["c"].iloc[-1]) + self.drift, now_utc


def test_live_evaluation_uses_real_entry_and_expiry_prices(tmp_path, bars_edge, bundle_edge):
    eng, s = _engine(bundle_edge, show_experimental=True)
    loop = AlertLoop(eng, _LivePriceFeed(bars_edge, drift=0.0), [], tmp_path, s)
    start = pd.Timestamp("2023-02-06 13:00", tz="UTC")
    for i in range(40):
        loop.step((start + pd.Timedelta(minutes=i, seconds=3)).to_pydatetime())
    evaluated = [a for a in loop.alerts if a.outcome and a.outcome.get("metodo")]
    assert evaluated, "debió evaluar alguna alerta experimental"
    for a in evaluated:
        assert a.outcome["metodo"] == "precio real de entrada y vencimiento"
        assert a.entry_price_live == pytest.approx(a.outcome["entrada"], abs=1e-6)
    # Si el bucle llega tarde al vencimiento, la alerta se marca no evaluable (no se inventa el precio).
    a = evaluated[0]
    a.outcome, a.evaluated_at = None, None
    loop.pending = [a]
    late = pd.Timestamp(a.entry_time_live) + pd.Timedelta(minutes=a.duration_min, seconds=45)
    loop._evaluate_pending(bars_edge.iloc[:0], late.to_pydatetime(), live_px=1.1)
    assert a.outcome["resultado"] == "no_evaluable"
    # Un precio de vencimiento que llega bastante ANTES del minuto no se usa: la alerta sigue pendiente.
    a.outcome = None
    loop.pending = [a]
    early = pd.Timestamp(a.entry_time_live) + pd.Timedelta(minutes=a.duration_min, seconds=-(EARLY_TOLERANCE_S + 3))
    loop._evaluate_pending(bars_edge.iloc[:0], early.to_pydatetime(), live_px=1.1)
    assert a.outcome is None and loop.pending == [a]


# ---------------------------------------------------------------------- auditoría local (2026-09-30)
def _steps(loop, start, n, jitter_s=None):
    for i in range(n):
        j = 0.0 if jitter_s is None else jitter_s[i % len(jitter_s)]
        t = start + pd.Timedelta(minutes=i, seconds=3) + pd.Timedelta(microseconds=round(j * 1e6))
        loop.step(t.to_pydatetime())


def test_millisecond_jitter_does_not_drop_live_alerts(tmp_path, bars_edge, bundle_edge):
    """Windows despierta el bucle con ±1 ms de desfase: antes ~50 % quedaban «no_evaluable (retraso 60 s)»."""
    eng, s = _engine(bundle_edge, show_experimental=True)
    loop = AlertLoop(eng, _LivePriceFeed(bars_edge, drift=0.0), [], tmp_path, s)
    _steps(loop, pd.Timestamp("2023-02-06 13:00", tz="UTC"), 60, jitter_s=[-0.0007, 0.0004, -0.0012, 0.0001, -0.0003])
    evaluated = [a for a in loop.alerts if a.outcome]
    assert len(evaluated) >= 10
    assert all(a.outcome["resultado"] != "no_evaluable" for a in evaluated)
    assert all(abs(a.outcome["duracion_real_s"] - 60) < 0.01 for a in evaluated)
    rows, bad = read_rows(tmp_path / "paper_ledger.jsonl")
    assert len(rows) == len(evaluated) and bad == 0


def test_state_json_is_strict_json_even_with_nan_evidence(tmp_path, bars_edge, bundle_edge):
    """El veredicto del periodo bloqueado tiene NaN; el navegador rechaza NaN y el panel quedaba en blanco."""
    from tradingbot.app.server import make_server

    b = copy.copy(bundle_edge)
    b.validation_status = "VALIDADO_HOLDOUT"
    b.validation_evidence = {"holdout": {"verdict": "X", "passed": [], "details": [{"hit": float("nan")}]}}
    eng, s = _engine(b, show_experimental=False)
    loop = AlertLoop(eng, ReplayFeed(bars_edge), [], tmp_path, s)
    _steps(loop, pd.Timestamp("2023-02-06 13:00", tz="UTC"), 5)

    def strict(c):
        raise ValueError(c)

    text = (tmp_path / "state.json").read_text(encoding="utf-8")
    state = json.loads(text, parse_constant=strict)
    assert state["model"]["validation_evidence"]["holdout"] == {"verdict": "X", "passed": []}
    # Un state.json antiguo con NaN también se sirve como JSON válido.
    (tmp_path / "state.json").write_text(text.replace('"passed": []', '"passed": [], "x": NaN'), encoding="utf-8")
    srv = make_server("127.0.0.1", 0, tmp_path, tmp_path / "results")
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    try:
        body = urllib.request.urlopen(f"http://127.0.0.1:{srv.server_address[1]}/api/state").read().decode()
        assert json.loads(body, parse_constant=strict)["model"]["validation_evidence"]["holdout"]["x"] is None
    finally:
        srv.shutdown()
        srv.server_close()


def test_holdout_validated_model_is_observed_without_flag(bars_edge, bundle_edge):
    """VALIDADO_HOLDOUT está «en observación»: con TB_SHOW_EXPERIMENTAL=false antes no se registraba nada."""
    b = copy.copy(bundle_edge)
    b.validation_status = "VALIDADO_HOLDOUT"
    eng, s = _engine(b, show_experimental=False)
    feed = ReplayFeed(bars_edge)
    statuses = set()
    for i in range(120):
        now = (pd.Timestamp("2023-02-06 13:00", tz="UTC") + pd.Timedelta(minutes=i, seconds=3)).to_pydatetime()
        a = eng.evaluate(feed.get(now)[0], now, RiskState())
        statuses.add(a.status)
        if a.status == NO_SIGNAL:
            assert "sin validar" not in a.no_signal_reason
    assert EXPERIMENTAL in statuses and SIGNAL not in statuses


def test_paused_monitor_keeps_observing_would_be_alerts(tmp_path, bars_edge, bundle_edge):
    """En pausa, las alertas que sí se habrían emitido se evalúan como hipotéticas (antes: «pendiente» eterno)."""
    eng, s = _engine(bundle_edge, show_experimental=True)
    feed = ReplayFeed(bars_edge)
    seen = {"con_direccion": 0, "sin_direccion": 0}
    for i in range(45):
        now = (pd.Timestamp("2023-02-06 13:00", tz="UTC") + pd.Timedelta(minutes=i, seconds=3)).to_pydatetime()
        bars = feed.get(now)[0]
        normal = eng.evaluate(bars, now, RiskState())
        paused = eng.evaluate(bars, now, RiskState(), monitor_status="PAUSADO")
        assert paused.status == PAUSED
        if normal.status == EXPERIMENTAL:
            assert paused.direction == normal.direction and "hipotética" in paused.no_signal_reason
            seen["con_direccion"] += 1
        else:
            assert paused.direction is None
            seen["sin_direccion"] += 1
    assert seen["con_direccion"] and seen["sin_direccion"]
    # En el bucle, la alerta hipotética queda pendiente, se evalúa y entra al libro como «shadow».
    loop = AlertLoop(eng, ReplayFeed(bars_edge), [], tmp_path, s)
    loop.monitor = evaluate_monitor([{"win": False, "tie": False, "prob": 0.6}] * 200, 0.5405)
    assert loop.monitor.status == "PAUSADO"
    _steps(loop, pd.Timestamp("2023-02-06 13:00", tz="UTC"), 30)
    rows, _ = read_rows(tmp_path / "paper_ledger.jsonl")
    assert rows and all(r["shadow"] for r in rows) and PAUSED in {r["status"] for r in rows}


def test_restart_recovers_results_and_closes_orphan_alerts(tmp_path, bars_edge, bundle_edge):
    eng, s = _engine(bundle_edge, show_experimental=True)
    loop = AlertLoop(eng, _LivePriceFeed(bars_edge, drift=0.0), [], tmp_path, s)
    start = pd.Timestamp("2023-02-06 13:00", tz="UTC")
    i = 0
    while i < 30 or not loop.pending:  # termina con al menos una alerta sin evaluar («se cierra el programa»)
        loop.step((start + pd.Timedelta(minutes=i, seconds=3)).to_pydatetime())
        i += 1
        assert i < 300
    orphans = {a.alert_id for a in loop.pending}
    loop2 = AlertLoop(eng, _LivePriceFeed(bars_edge, drift=0.0), [], tmp_path, s)
    assert len(loop2.ledger.trades) == len(loop.ledger.trades) > 0
    assert loop2.monitor.n == loop.monitor.n and loop2.ledger.balance == loop.ledger.balance
    events = [json.loads(l) for l in open(tmp_path / "events.jsonl", encoding="utf-8")]
    closed = {e["alert_id"] for e in events if e["event"] == "evaluated"
              and e["outcome"].get("motivo", "").startswith("reinicio")}
    assert closed == orphans
    # Una tercera instancia ya no encuentra alertas abiertas.
    AlertLoop(eng, _LivePriceFeed(bars_edge, drift=0.0), [], tmp_path, s)
    events = [json.loads(l) for l in open(tmp_path / "events.jsonl", encoding="utf-8")]
    assert sum(1 for e in events if e.get("outcome", {}).get("motivo", "").startswith("reinicio")) == len(orphans)


def test_runtime_lock_blocks_second_live_instance(tmp_path):
    a, b = RuntimeLock(tmp_path), RuntimeLock(tmp_path)
    assert a.acquire()
    try:
        assert not b.acquire()
    finally:
        a.release()
    assert b.acquire()
    b.release()


def test_ack_is_idempotent_and_survives_state_rewrite(tmp_path, bars_edge, bundle_edge):
    from tradingbot.app.server import make_server

    eng, s = _engine(bundle_edge, show_experimental=True)
    loop = AlertLoop(eng, ReplayFeed(bars_edge), [], tmp_path, s)
    start = pd.Timestamp("2023-02-06 13:00", tz="UTC")
    _steps(loop, start, 10)
    srv = make_server("127.0.0.1", 0, tmp_path, tmp_path / "results")
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"

    def ack(aid):
        req = urllib.request.Request(base + "/api/ack", data=json.dumps({"alert_id": aid}).encode(),
                                     headers={"Content-Type": "application/json"}, method="POST")
        return json.loads(urllib.request.urlopen(req).read())

    try:
        aid = json.loads(urllib.request.urlopen(base + "/api/state").read())["alerts"][0]["alert_id"]
        before = (tmp_path / "state.json").read_bytes()
        first = ack(aid)
        second = ack(aid)
        assert second["ya_recibida"] and second["received_at"] == first["received_at"]
        assert (tmp_path / "state.json").read_bytes() == before  # el panel no escribe state.json
        assert len(read_rows(tmp_path / "acks.jsonl")[0]) == 1
        loop.step((start + pd.Timedelta(minutes=10, seconds=3)).to_pydatetime())  # tbot live reescribe el estado
        st = json.loads(urllib.request.urlopen(base + "/api/state").read())
        assert next(a for a in st["alerts"] if a["alert_id"] == aid)["received_at"] == first["received_at"]
    finally:
        srv.shutdown()
        srv.server_close()


@pytest.mark.skipif(os.name != "nt", reason="SO_REUSEADDR solo permite dos paneles en el mismo puerto en Windows")
def test_second_panel_on_same_port_fails_on_windows(tmp_path):
    from tradingbot.app.server import make_server

    srv = make_server("127.0.0.1", 0, tmp_path, tmp_path)
    try:
        with pytest.raises(OSError):
            make_server("127.0.0.1", srv.server_address[1], tmp_path, tmp_path).server_close()
    finally:
        srv.server_close()


def test_damaged_ledger_line_is_skipped_and_isolated(tmp_path):
    p = tmp_path / "paper_ledger.jsonl"
    good = {"time": "t", "alert_id": "a", "model_id": "M", "pnl": 0.85, "win": True, "tie": False, "shadow": True}
    p.write_text(json.dumps(good) + "\n" + '{"time": "t", "alert_id": "b", "pn', encoding="utf-8")  # apagón
    rows, bad = read_rows(p)
    assert len(rows) == 1 and bad == 1
    a = Alert(instrument="X", status=EXPERIMENTAL, price_source="", broker="", duration_min=1, direction="sube",
              decision_time=datetime(2026, 1, 1, tzinfo=timezone.utc), prob=0.6, model_id="M")
    PaperLedger(p).record(a, -1.0, False, False, True, method=LIVE_METHOD)
    rows, bad = read_rows(p)
    assert len(rows) == 2 and bad == 1 and rows[-1]["model_id"] == "M" and rows[-1]["method"] == LIVE_METHOD


def test_cycle_errors_and_gaps_are_recorded(tmp_path, bars_edge, bundle_edge):
    eng, s = _engine(bundle_edge, show_experimental=True)
    loop = AlertLoop(eng, ReplayFeed(bars_edge), [], tmp_path, s)
    t0 = pd.Timestamp("2023-02-06 13:00:03", tz="UTC")
    loop.step(t0.to_pydatetime())
    loop.step((t0 + pd.Timedelta(minutes=6)).to_pydatetime())  # p. ej. el PC estuvo suspendido
    loop.note_error(RuntimeError("red caída"), (t0 + pd.Timedelta(minutes=7)).to_pydatetime())
    events = [json.loads(l) for l in open(tmp_path / "events.jsonl", encoding="utf-8")]
    gap = next(e for e in events if e["event"] == "gap")
    assert gap["segundos"] == 360
    assert any(e["event"] == "cycle_failed" and "red caída" in e["error"] for e in events)
    assert "red caída" in json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))["last_error"]["error"]


class _FlakyPriceFeed(_LivePriceFeed):
    def current_price(self, now_utc):
        raise ConnectionError("ticker caído")


def test_live_mode_without_real_entry_price_is_not_evaluated_with_candles(tmp_path, bars_edge, bundle_edge):
    """Antes se usaba el método optimista de velas y se mezclaba sin marca en el veredicto."""
    eng, s = _engine(bundle_edge, show_experimental=True)
    loop = AlertLoop(eng, _FlakyPriceFeed(bars_edge, drift=0.0), [], tmp_path, s)
    _steps(loop, pd.Timestamp("2023-02-06 13:00", tz="UTC"), 40)
    evaluated = [a for a in loop.alerts if a.outcome]
    assert evaluated and all(a.outcome["motivo"].startswith("sin precio real de entrada") for a in evaluated)
    assert not (tmp_path / "paper_ledger.jsonl").exists()


def test_live_verdict_counts_only_one_model_with_real_prices(tmp_path, bars_edge, bundle_edge, capsys):
    from tradingbot.cli import main

    out = tmp_path / "verdict.json"
    reg = _register(tmp_path, bundle_edge.model_id)
    args = ["live-verdict", "--symbol", "SYNTH", "--model", "logit", "--runtime", str(tmp_path), "--out", str(out),
            "--observation", str(reg)]
    assert main(args) == 2  # sin libro: mensaje claro, no un error de Python
    assert "No hay alertas evaluadas" in capsys.readouterr().out
    assert main([*args[:4], "gbm", *args[5:]]) == 2  # otro modelo distinto del registrado
    eng, s = _engine(bundle_edge, show_experimental=True)
    loop = AlertLoop(eng, _LivePriceFeed(bars_edge, drift=0.0), [], tmp_path, s)
    _steps(loop, pd.Timestamp("2023-02-06 13:00", tz="UTC"), 60)
    n_real = sum(1 for t in loop.ledger.trades if not t["tie"])
    p = tmp_path / "paper_ledger.jsonl"
    other = {"model_id": "SYNTH-h1-gbm-2023-01-31", "method": LIVE_METHOD, "pnl": 0.85, "win": True, "tie": False,
             "payout": 0.85, "shadow": True, "policy": POL}
    with open(p, "a", encoding="utf-8") as fh:  # otro modelo, sin modelo y otro entrenamiento del mismo modelo
        fh.write("".join(json.dumps(r) + "\n" for r in (other, {**other, "model_id": None},
                                                         {**other, "model_id": "SYNTH-h1-logit-2024-01-01"})))
    assert main(args) == 0
    v = json.loads(out.read_text(encoding="utf-8"))
    assert v["model_id"] == bundle_edge.model_id and v["n"] == n_real and v["horizon"] == 1
    assert v["excluidas"]["de_otro_modelo_o_sin_modelo"] == 3
    assert v["breakeven"] == pytest.approx(1 / 1.85)
    assert v["medicion"]["duracion_real_s"]["mediana"] == pytest.approx(60, abs=0.01)
    assert sum(h["n"] for h in v["medicion"]["por_hora_bogota"].values()) == n_real


def test_research_verdict_shows_holdout_result(tmp_path):
    from tradingbot.app.server import research_verdict

    fz = tmp_path / "frozen.json"
    fz.write_text(json.dumps({"verdict": "HAY CANDIDATAS (pendiente periodo bloqueado)", "candidates": [{}]}))
    (tmp_path / "holdout").mkdir()
    (tmp_path / "holdout" / "verdict.json").write_text(
        '{"verdict": "VALIDADAS", "n_candidates": 1, "passed": [{"symbol": "BTCUSDT"}], "details": [{"hit": NaN}]}')
    r = research_verdict(tmp_path, fz)
    assert r["holdout_verdict"] == "VALIDADAS" and r["holdout_passed"] == [{"symbol": "BTCUSDT"}]


def test_alert_text_separates_probability_from_group_hit_rate():
    a = Alert(instrument="BTC/USDT", status=EXPERIMENTAL, price_source="x", broker="y", duration_min=1,
              decision_time=datetime(2026, 1, 1, 15, tzinfo=timezone.utc), direction="sube",
              prob=0.716, prob_bin_hit=0.753, prob_lo=0.724, prob_hi=0.782, prob_n=900, payout=0.85)
    assert "probabilidad: 71.6% | acierto histórico de señales parecidas: 75.3% [72.4%–78.2%]" in a.one_line()
    assert "Acierto histórico de señales parecidas: 75.3% [72.4%–78.2%] (IC90, n=900)" in a.format_text()


# ---------------------------------------------------------------------- revisión final (2026-10-02)
def test_note_error_never_raises_even_if_the_log_is_locked(tmp_path, bars_edge, bundle_edge):
    """Si events.jsonl está bloqueado por otro programa, el bucle debe seguir (antes se cerraba)."""
    eng, s = _engine(bundle_edge, show_experimental=True)
    loop = AlertLoop(eng, ReplayFeed(bars_edge), [], tmp_path, s)

    def locked(*_a, **_k):
        raise PermissionError("events.jsonl bloqueado")

    loop.log.write = locked
    loop.note_error(PermissionError("events.jsonl bloqueado"))  # no debe lanzar
    assert "bloqueado" in loop.last_error["error"]


def test_line_cut_inside_a_utf8_character_does_not_block_restart(tmp_path, bars_edge, bundle_edge):
    eng, s = _engine(bundle_edge, show_experimental=True)
    loop = AlertLoop(eng, _LivePriceFeed(bars_edge, drift=0.0), [], tmp_path, s)
    _steps(loop, pd.Timestamp("2023-02-06 13:00", tz="UTC"), 30)
    for name in ("paper_ledger.jsonl", "events.jsonl"):  # apagón a mitad de «—» (E2 80 94)
        with open(tmp_path / name, "ab") as fh:
            fh.write('{"status": "EXPERIMENTAL '.encode("utf-8") + "—".encode("utf-8")[:1])
    rows, bad = read_rows(tmp_path / "paper_ledger.jsonl")
    assert bad == 1 and len(rows) == len(loop.ledger.trades)
    loop2 = AlertLoop(eng, _LivePriceFeed(bars_edge, drift=0.0), [], tmp_path, s)  # antes: UnicodeDecodeError
    assert len(loop2.ledger.trades) == len(loop.ledger.trades)
    events = [e for e in jsonutil.iter_jsonl(tmp_path / "events.jsonl")]
    assert events.count(None) == 1 and any(e and e["event"] == "ledger_damaged_lines" for e in events)


class _SlowEntryFeed(_LivePriceFeed):
    """El precio llega con una demora HTTP distinta en cada ciclo (2,6 s y 0,4 s alternados)."""

    def __init__(self, bars, delays):
        super().__init__(bars, drift=0.0)
        self.delays, self.i = delays, 0

    def current_price(self, now_utc):
        px, _ = super().current_price(now_utc)
        d = self.delays[self.i % len(self.delays)]
        self.i += 1
        return px, now_utc + pd.Timedelta(seconds=d).to_pytimedelta()


def test_variable_http_delay_does_not_drop_alerts(tmp_path, bars_edge, bundle_edge):
    """La tolerancia se mide con el reloj del ciclo; la duración real (57,8–62,2 s) se anota."""
    eng, s = _engine(bundle_edge, show_experimental=True)
    loop = AlertLoop(eng, _SlowEntryFeed(bars_edge, [2.6, 0.4]), [], tmp_path, s)
    _steps(loop, pd.Timestamp("2023-02-06 13:00", tz="UTC"), 60)
    evaluated = [a for a in loop.alerts if a.outcome]
    assert len(evaluated) >= 10 and all(a.outcome["resultado"] != "no_evaluable" for a in evaluated)
    assert {round(abs(a.outcome["retraso_s"]), 1) for a in evaluated} == {2.2}
    # Con 15 s de diferencia entre demoras, la duración real queda fuera de 60 ± 10 s: se dice así.
    loop = AlertLoop(eng, _SlowEntryFeed(bars_edge, [15.0, 0.0]), [], tmp_path / "b", s)
    _steps(loop, pd.Timestamp("2023-02-06 13:00", tz="UTC"), 60)
    reasons = {a.outcome.get("motivo", "") for a in loop.alerts if a.outcome}
    assert any(r.startswith("duración real") for r in reasons)


def test_panel_stale_marker_ignores_failed_cycles(tmp_path, bars_edge, bundle_edge):
    eng, s = _engine(bundle_edge, show_experimental=True)
    loop = AlertLoop(eng, ReplayFeed(bars_edge), [], tmp_path, s)
    _steps(loop, pd.Timestamp("2023-02-06 13:00", tz="UTC"), 2)
    ok = json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))
    loop.note_error(ConnectionError("red caída"))
    after = json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))
    assert after["last_ok_at"] == ok["last_ok_at"] and after["updated_at"] >= ok["updated_at"]
    assert "red caída" in after["last_error"]["error"]


def test_holdout_verdict_of_another_study_is_ignored(tmp_path):
    from tradingbot.app.server import research_verdict

    fz = tmp_path / "frozen.json"
    fz.write_text(json.dumps({"verdict": "HAY CANDIDATAS (pendiente periodo bloqueado)", "git_sha": "nuevo",
                              "config_hash": "h", "candidates": [{"symbol": "EURUSD", "horizon": 1, "model": "logit"}]}))
    (tmp_path / "holdout").mkdir()
    hv = tmp_path / "holdout" / "verdict.json"
    hv.write_text(json.dumps({"verdict": "VALIDADAS", "frozen_git_sha": "viejo", "config_hash": "h",
                              "passed": [{"symbol": "EURUSD", "horizon": 1, "model": "logit"}]}))
    r = research_verdict(tmp_path, fz)
    assert r["holdout_other_study"] and "holdout_verdict" not in r
    assert validation_status_for("EURUSD", 1, "logit", fz, hv)[0] == "CANDIDATO_DEV"


def test_ack_after_a_cut_line_is_not_lost(tmp_path, bars_edge, bundle_edge):
    from tradingbot.app.server import first_acks, make_server

    eng, s = _engine(bundle_edge, show_experimental=True)
    loop = AlertLoop(eng, ReplayFeed(bars_edge), [], tmp_path, s)
    _steps(loop, pd.Timestamp("2023-02-06 13:00", tz="UTC"), 3)
    (tmp_path / "acks.jsonl").write_text('{"event": "received", "ti', encoding="utf-8")  # apagón
    srv = make_server("127.0.0.1", 0, tmp_path, tmp_path / "results")
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    try:
        aid = loop.alerts[0].alert_id
        req = urllib.request.Request(f"http://127.0.0.1:{srv.server_address[1]}/api/ack",
                                     data=json.dumps({"alert_id": aid}).encode(), method="POST")
        first = json.loads(urllib.request.urlopen(req).read())
        assert first_acks(tmp_path)[aid] == first["received_at"]
    finally:
        srv.shutdown()
        srv.server_close()


def test_live_verdict_uses_the_registered_contract_not_the_env(tmp_path):
    """Si el .env cambiara el pago (p. ej. 0,92 de una plataforma), ni el umbral ni la muestra cambian."""
    from tradingbot.cli import main

    mid = "SYNTH-h1-logit-2023-01-31-abc123"
    reg = _register(tmp_path, mid)
    row = {"model_id": mid, "method": LIVE_METHOD, "shadow": True, "policy": POL, "payout": 0.85}
    rows = ([{**row, "win": True, "tie": False, "pnl": 0.85}] * 58 + [{**row, "win": False, "tie": False, "pnl": -1.0}] * 32
            + [{**row, "win": False, "tie": True, "pnl": 0.0}] * 10
            + [{**row, "policy": {**POL, "payout": 0.92}, "payout": 0.92, "win": True, "tie": False, "pnl": 0.92}] * 40)
    (tmp_path / "paper_ledger.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    out = tmp_path / "v.json"
    assert main(["live-verdict", "--symbol", "SYNTH", "--model", "logit", "--runtime", str(tmp_path),
                 "--out", str(out), "--observation", str(reg)]) == 0
    v = json.loads(out.read_text(encoding="utf-8"))
    assert v["breakeven"] == pytest.approx(1 / 1.85) and v["n"] == 90
    assert v["excluidas"]["politica_distinta_a_la_registrada"] == 40


def test_registered_policy_overrides_env():
    s = Settings(payout=0.92, ev_margin=0.0, feed_latency_s=2.0, max_staleness_s=90.0)
    reg = {**POL, "feed_latency_s": 1.0, "max_staleness_s": 11.0}
    changes = apply_policy(s, reg)
    assert policy_of(s) == reg and any(c.startswith("payout") for c in changes)
    assert any(c.startswith("ev_margin") for c in changes) and len(changes) == 4


class _FakeBinance:
    """Sesión falsa de la API de klines: velas de 1 min hasta la hora de «Binance» (`server_now`)."""

    def __init__(self, server_now):
        self.server_now, self.calls = server_now, []

    def get(self, url, params=None, timeout=None):
        self.calls.append(dict(params or {}))
        open_now = int(self.server_now.timestamp() // 60 * 60 * 1000)  # vela en curso
        end = min(params.get("endTime", open_now), open_now)
        last = end // 60000 * 60000
        opens = [last - 60000 * i for i in range(params["limit"])][::-1]
        rows = [[t, "100", "101", "99", "100.5", "2", t + 59999, "0", 5, "0", "0", "0"] for t in opens]

        class R:
            def raise_for_status(self):
                pass

            def json(self):
                return rows
        return R()


def test_binance_feed_keeps_history_and_uses_server_clock(monkeypatch):
    from tradingbot.live import feeds

    srv = pd.Timestamp("2026-10-03 15:00:01", tz="UTC")
    fake = _FakeBinance(srv)
    feed = BinancePollingFeed("BTCUSDT", session=fake)
    feed.offset_s = 2.0  # el PC va 2 s atrasado: según su reloj aún son las 14:59:59
    monkeypatch.setattr(feeds, "utcnow", lambda: (fake.server_now - pd.Timedelta(seconds=2)).to_pydatetime())
    bars, _ = feed.get()
    assert len(fake.calls) == 3 and len(bars) >= 1440  # primera vez: ~2 000 velas
    assert bars.index[-1] == pd.Timestamp("2026-10-03 14:59", tz="UTC")  # cerrada según Binance
    fake.server_now += pd.Timedelta(minutes=1)
    bars, _ = feed.get()
    assert len(fake.calls) == 4 and fake.calls[-1]["limit"] == 5  # después: solo las últimas velas
    assert bars.index[-1] == pd.Timestamp("2026-10-03 15:00", tz="UTC")
    fake.server_now += pd.Timedelta(minutes=30)  # hueco (p. ej. suspensión): se vuelve a descargar todo
    bars, _ = feed.get()
    assert len(fake.calls) == 7 and bars.index.to_series().diff().max() == pd.Timedelta(minutes=1)


def test_repeated_decision_candle_is_not_counted_twice(tmp_path, bars_edge, bundle_edge):
    """Si no llega la vela nueva, el motor repetiría la decisión anterior con 60 s de retraso."""

    class _Frozen(_LivePriceFeed):
        frozen = None

        def get(self, now_utc, lookback=2000):
            return super().get(self.frozen or now_utc, lookback)

    eng, s = _engine(bundle_edge, show_experimental=True)
    feed = _Frozen(bars_edge, drift=0.0)
    loop = AlertLoop(eng, feed, [], tmp_path, s)
    t = pd.Timestamp("2023-02-06 13:00:03", tz="UTC")
    for _ in range(240):
        if loop.step(t.to_pydatetime()).status == EXPERIMENTAL:
            break
        t += pd.Timedelta(minutes=1)
    feed.frozen = t.to_pydatetime()  # el minuto siguiente no llega la vela nueva
    again = loop.step((t + pd.Timedelta(minutes=1)).to_pydatetime())
    assert again.status == NO_SIGNAL and "decisión repetida" in again.no_signal_reason


def test_historical_price_feed_uses_registered_timing(bars_edge, bundle_edge, tmp_path):
    """Enmienda 2: entrada = último precio antes de cierre + 2 s; vencimiento = 60 s después."""
    from tradingbot.live.replay import HistoricalPriceFeed

    t0 = pd.Timestamp("2023-02-06 13:00", tz="UTC")
    secs = pd.date_range(t0, periods=600, freq="s")
    closes = pd.Series(np.arange(600, dtype=float), index=secs)  # precio = segundos desde t0
    feed = HistoricalPriceFeed(bars_edge, closes, entry_delay_s=2.0)
    px, t = feed.current_price((t0 + pd.Timedelta(seconds=61)).to_pydatetime())  # ciclo: cierre 13:01 + 1 s
    assert px == 61 and pd.Timestamp(t) == t0 + pd.Timedelta(seconds=62)  # vela 13:01:01–13:01:02
    px30, _ = HistoricalPriceFeed(bars_edge, closes, entry_delay_s=30).current_price(
        (t0 + pd.Timedelta(seconds=61)).to_pydatetime())
    assert px30 == 89  # último precio antes de 13:01:30
    gap = closes.drop(closes.index[100:120])
    with pytest.raises(ValueError):
        HistoricalPriceFeed(bars_edge, gap, entry_delay_s=2.0).current_price((t0 + pd.Timedelta(seconds=118)).to_pydatetime())
    # Solo se ven velas de 1 min ya publicadas (cierre + 0,3 s) y la búsqueda no recorre todo el historial.
    bars, _ = feed.get((t0 + pd.Timedelta(seconds=61)).to_pydatetime())
    assert bars.index[-1] == t0 and len(bars) == 2000
    # Con el bucle real: entrada a +2 s, vencimiento a +62 s, duración exacta de 60 s.
    eng, s = _engine(bundle_edge, show_experimental=True)
    long_closes = pd.Series(np.linspace(1.1, 1.2, 4 * 3600), index=pd.date_range(t0, periods=4 * 3600, freq="s"))
    loop = AlertLoop(eng, HistoricalPriceFeed(bars_edge, long_closes), [], tmp_path, s)
    for i in range(60):
        loop.step((t0 + pd.Timedelta(minutes=i + 1, seconds=1)).to_pydatetime())
    ev = [a for a in loop.alerts if a.outcome and a.outcome.get("metodo")]
    assert ev and all(a.outcome["duracion_real_s"] == 60 for a in ev)
    assert all(r["entrada_tras_cierre_s"] == 2 for r in loop.ledger.trades)


def test_event_log_never_raises(tmp_path, monkeypatch):
    from tradingbot.live import runner

    log = runner.EventLog(tmp_path)

    def locked(*_a, **_k):
        raise PermissionError("bloqueado")

    monkeypatch.setattr(runner.jsonutil, "append_line", locked)
    log.write("generated", extra=1)  # no debe lanzar
    assert log.failed == 1


def test_live_verdict_reports_unevaluable_alerts(tmp_path, bars_edge, bundle_edge):
    from tradingbot.cli import main

    class _OneInThree(_LivePriceFeed):
        n = 0

        def current_price(self, now_utc):
            self.n += 1
            if self.n % 3 == 0:
                raise ConnectionError("ticker caído")
            return super().current_price(now_utc)

    eng, s = _engine(bundle_edge, show_experimental=True)
    loop = AlertLoop(eng, _OneInThree(bars_edge, drift=0.0), [], tmp_path, s)
    _steps(loop, pd.Timestamp("2023-02-06 13:00", tz="UTC"), 60)
    lost = sum(1 for a in loop.alerts if a.outcome and a.outcome["resultado"] == "no_evaluable")
    out = tmp_path / "v.json"
    reg = _register(tmp_path, bundle_edge.model_id)
    assert main(["live-verdict", "--symbol", "SYNTH", "--model", "logit", "--runtime", str(tmp_path),
                 "--out", str(out), "--observation", str(reg)]) == 0
    v = json.loads(out.read_text(encoding="utf-8"))
    assert lost > 0 and v["no_evaluables"]["total"] == lost


def test_model_id_identifies_the_training(bars_edge):
    train = bars_edge[bars_edge.index < pd.Timestamp("2023-02-01", tz="UTC")]
    a = fit_bundle(train, "SYNTH", 1, "logit", "synthetic", 1e-5, synthetic=True)
    b = fit_bundle(train, "SYNTH", 1, "logit", "synthetic", 1e-5, synthetic=True)
    c = fit_bundle(train[train.index >= pd.Timestamp("2023-01-12", tz="UTC")], "SYNTH", 1, "logit", "synthetic",
                   1e-5, synthetic=True)  # otra ventana que termina el mismo día
    assert a.trained_to[:10] == c.trained_to[:10]
    assert a.model_id == b.model_id and a.model_id != c.model_id


def test_fixed_sample_makes_daily_checks_harmless():
    """Aclaración 2: el veredicto usa siempre las primeras 200 alertas sin empate, se consulte cuando se consulte."""
    from tradingbot.signals.monitor import fixed_sample

    rows = [{"time": f"2026-10-{d:02d}T{h:02d}:00", "win": (d * 24 + h) % 3 != 0, "tie": h == 5, "pnl": 0.0}
            for d in range(4, 20) for h in range(24)]
    s = fixed_sample(rows, 200)
    assert sum(1 for r in s if not r["tie"]) == 200 and s == sorted(s, key=lambda r: r["time"])
    assert fixed_sample(rows + [{"time": "2026-11-01T00:00", "win": True, "tie": False}], 200) == s
    assert len(fixed_sample(rows[:50], 200)) == 50  # aún no hay muestra: el veredicto será insuficiente


def test_live_verdict_sample_completed_after_eight_weeks_does_not_pass(tmp_path):
    from tradingbot.cli import main

    mid = "SYNTH-h1-logit-2023-01-31-abc123"
    t0 = pd.Timestamp("2026-10-03", tz="UTC")
    rows = [{"model_id": mid, "method": LIVE_METHOD, "payout": 0.85, "policy": POL, "shadow": True,
             "time": (t0 + pd.Timedelta(minutes=25 * i)).isoformat(),  # ~58 alertas/día → 60 días para 3 500
             "win": i % 10 < 7, "tie": False, "pnl": 0.85 if i % 10 < 7 else -1.0} for i in range(LIVE_SAMPLE_N)]
    (tmp_path / "paper_ledger.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    out = tmp_path / "v.json"
    args = ["live-verdict", "--symbol", "SYNTH", "--model", "logit", "--runtime", str(tmp_path), "--out", str(out),
            "--observation", str(_register(tmp_path, mid))]
    assert main(args) == 0
    v = json.loads(out.read_text(encoding="utf-8"))
    assert v["n"] == LIVE_SAMPLE_N and v["hit_lo95"] > v["breakeven"] and not v["passed"]
    assert any("no concluyente" in r for r in v["reasons"])
    # La misma muestra reunida en 3 semanas sí aprobaría.
    fast = [{**r, "time": (t0 + pd.Timedelta(minutes=9 * i)).isoformat()} for i, r in enumerate(rows)]
    (tmp_path / "paper_ledger.jsonl").write_text("".join(json.dumps(r) + "\n" for r in fast), encoding="utf-8")
    assert main(args) == 0 and json.loads(out.read_text(encoding="utf-8"))["passed"]


def test_observed_model_replicates_validated_policy_without_extra_filter(bars_edge, bundle_edge):
    """La política validada (B/BN) no incluía el filtro prob_lo > umbral: en observación solo se anota."""
    b = copy.copy(bundle_edge)
    b.validation_status = "VALIDADO_HOLDOUT"
    eng_obs, _ = _engine(b, show_experimental=False)
    eng_demo, _ = _engine(bundle_edge, show_experimental=True)  # no validado: el filtro sigue bloqueando
    feed = ReplayFeed(bars_edge)
    flagged = 0
    for i in range(240):
        now = (pd.Timestamp("2023-02-06 13:00", tz="UTC") + pd.Timedelta(minutes=i, seconds=3)).to_pydatetime()
        bars = feed.get(now)[0]
        obs, demo = eng_obs.evaluate(bars, now, RiskState()), eng_demo.evaluate(bars, now, RiskState())
        if obs.status == EXPERIMENTAL:
            assert obs.ev >= 0.02 and obs.ic_filter_ok is not None
            if not obs.ic_filter_ok:
                flagged += 1
                assert demo.status == NO_SIGNAL and "acierto histórico" in demo.no_signal_reason
        if demo.status == EXPERIMENTAL:
            assert obs.status == EXPERIMENTAL and demo.ic_filter_ok
    assert flagged > 0


def test_one_line_spot_contract_without_payout():
    a = Alert(instrument="EUR/USD", status=NO_SIGNAL, price_source="x", broker="y", contract="contado",
              payout_verified=True, decision_time=datetime(2026, 1, 1, tzinfo=timezone.utc), duration_min=1)
    assert "pago: no aplica" in a.one_line()  # antes: TypeError en cada ciclo
