"""Modo de práctica de los event contracts de OKX (Estudios 54 y 55): nombres, costos, turnos, precio y resultado oficial."""

import json

import numpy as np
import pandas as pd
import pytest

from tradingbot.data import synthetic
from tradingbot.data.clean import to_canonical
from tradingbot.live import okx_eventos as ok
from tradingbot.live.anticipada import aviso_texto
from tradingbot.research.calibration import Calibrator
from tradingbot.research.study16 import PARTIAL
from tradingbot.research.study42 import COMP


def test_instrument_name_uses_utc_plus_8_like_okx():
    t = pd.Timestamp("2026-11-07 22:50", tz="UTC")
    assert ok.inst_id("ETHUSDT", t) == "ETH-UPDOWN-5MIN-261108-0650-0655"
    assert ok.inst_id("BTCUSDT", pd.Timestamp("2026-11-07 15:55", tz="UTC")) == "BTC-UPDOWN-5MIN-261107-2355-0000"


def test_cost_and_equivalent_payout():
    assert ok.costo(0.52) == pytest.approx(0.52 + 0.045 * 0.52 * 0.48)
    c = ok.costo(0.52)
    assert ok.pago_equivalente(0.52) == pytest.approx((1 - c) / c)
    # con esos valores, el blitz avisa si p ≥ (1 + margen) / (1 + pago) = (costo + 0,02) / 1
    p_min = (1 + ok.margen_equivalente()) / (1 + ok.pago_equivalente())
    assert p_min == pytest.approx(c + 0.02)
    assert ok.proxima_decision(pd.Timestamp("2026-11-07 22:50", tz="UTC")) == pd.Timestamp("2026-11-07 22:54", tz="UTC")


class _Model:
    def __init__(self, p):
        self.p = p

    def predict_proba(self, X):
        return np.column_stack([1 - np.full(len(X), self.p), np.full(len(X), self.p)])


def _bundle(p=0.7):
    rng = np.random.default_rng(0)
    raw = rng.uniform(0, 1, 5000)
    cal = Calibrator().fit(raw, (rng.uniform(0, 1, 5000) < raw).astype(int))
    return {"model": _Model(p), "calibrator": cal, "features": ok.FEATURES + PARTIAL + COMP, "k": 50, "latencia": 10,
            "duracion_min": 5, "q": 0.0, "payout": ok.pago_equivalente(), "ev_margin": ok.margen_equivalente(),
            "model_id": "PRUEBA-OKX", "symbol": "ETHUSDT"}


@pytest.fixture(scope="module")
def bars():
    b, _ = to_canonical(synthetic.generate(start="2024-01-01", days=3, phi=0.0, seed=1))
    return b


class _Eventos:
    def __init__(self, ask=0.51, bid=0.49, outcome="1"):
        self.ask, self.bid, self.outcome = ask, bid, outcome

    def precio_compra(self, inst, lado):
        return self.ask if lado == 1 else round(1 - self.bid, 6)

    def resultado(self, symbol, inst, after_ms=None):
        return {"outcome": self.outcome, "partida": 100.0, "liquidacion": 101.0}


def _loop(tmp_path, bars, eventos, minute):
    sec_idx = pd.date_range(minute, periods=50, freq="s")
    c = 1.1 + np.cumsum(np.random.default_rng(0).normal(0, 1e-5, 50))
    sec = pd.DataFrame({"o": c, "h": c + 1e-6, "l": c - 1e-6, "c": c, "v": 1.0, "tb": 0.6, "n": 2.0}, index=sec_idx)
    t1 = minute - pd.Timedelta(minutes=1)
    closes = bars["c"][bars.index <= t1].iloc[-75:]

    class _Feed:
        offset_s, session = 0.0, None

        def get(self, now=None):
            return bars[bars.index <= t1], now

        def server_now(self):
            return minute + pd.Timedelta(seconds=50.3)

    class _Sec:
        def get(self, start, now, limit=120):
            return sec

    class _V:
        def recent(self, t):
            return {"bybit": closes * (1 - 1e-4), "okx": closes * (1 + 5e-5)}

    return ok.OkxLoop(_bundle(), tmp_path, feed=_Feed(), secfeed=_Sec(), venues=_V(), sound=False, eventos=eventos)


def test_loop_decides_only_before_each_window_and_checks_the_price(tmp_path, bars):
    grid = bars.index[-10]
    while (grid.minute + 1) % 5:  # un minuto de decisión dentro de los datos sintéticos
        grid -= pd.Timedelta(minutes=1)
    bars_g = bars[bars.index <= grid - pd.Timedelta(minutes=1)]
    loop = _loop(tmp_path, bars_g, _Eventos(), grid)
    off = loop.step((grid - pd.Timedelta(minutes=1) + pd.Timedelta(seconds=50.3)).to_pydatetime())
    assert off["estado"] == "fuera de turno"
    d = loop.step((grid + pd.Timedelta(seconds=50.3)).to_pydatetime())
    assert d["estado"] == "señal" and d["lado"] == 1 and d["precio_compra"] == 0.51
    ventana = grid + pd.Timedelta(minutes=1)
    assert d["ventana"] == ventana.isoformat() and d["instrumento"] == ok.inst_id("ETHUSDT", ventana)
    assert d["vence"] == (ventana + pd.Timedelta(minutes=5)).isoformat()
    assert d["ev_accion"] == pytest.approx(d["p"] - ok.costo(0.51), abs=1e-4)
    texto = aviso_texto(d, "okx")
    fin = (ventana + pd.Timedelta(minutes=5)).tz_convert("America/Bogota")
    assert texto.startswith("🔔 OKX ETH 5 min: ↑ SUBE") and "Sin dinero real" in texto
    assert f"Compra «Al alza» en la pestaña «{fin:%H:%M}»" in texto  # como la web de OKX en español
    limite = (ventana - pd.Timedelta(seconds=3)).tz_convert("America/Bogota")  # OKX retira los precios 1–2 s antes
    assert f"ANTES de las {limite:%H:%M:%S}" in texto
    caro = _loop(tmp_path / "caro", bars_g, _Eventos(ask=0.60), grid)
    x = caro.step((grid + pd.Timedelta(seconds=50.3)).to_pydatetime())
    assert x["estado"] == "sin señal" and "0.6" in x["motivo"]


def test_main_coin_reads_its_own_prices(tmp_path):
    """Regresión (registro de errores 56): con ETH como moneda principal, el bucle leía velas, segundos y bolsas de
    BTC. Cada moneda debe leer sus propios datos."""
    loop = ok.OkxLoop(_bundle(), tmp_path, sound=False, extra=[{"symbol": "BTCUSDT", "bundle": {**_bundle(),
                                                                                                "symbol": "BTCUSDT"}}])
    eth, btc = loop.by_symbol["ETHUSDT"], loop.by_symbol["BTCUSDT"]
    assert (eth["feed"].symbol, eth["sec"].symbol, eth["venues"].symbol) == ("ETHUSDT",) * 3
    assert (btc["feed"].symbol, btc["sec"].symbol, btc["venues"].symbol) == ("BTCUSDT",) * 3


def test_reference_is_the_official_okx_result(tmp_path, bars):
    t = pd.Timestamp("2026-11-07 22:49", tz="UTC")
    row = {"evento": "aviso", "alert_id": "a1", "vela": t.isoformat(), "lado": -1, "p": 0.6, "ev": 0.05,
           "decidido": (t + pd.Timedelta(seconds=50)).isoformat(), "cierre": (t + pd.Timedelta(minutes=1)).isoformat(),
           "vence": (t + pd.Timedelta(minutes=6)).isoformat(), "symbol": "ETHUSDT",
           "instrumento": "ETH-UPDOWN-5MIN-261108-0650-0655"}
    (tmp_path / "senales.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")
    loop = _loop(tmp_path, bars, _Eventos(outcome="1"), bars.index[-1])
    assert loop.fill_references((t + pd.Timedelta(minutes=6, seconds=5)).to_pydatetime()) == 0  # aún no vence
    assert loop.fill_references((t + pd.Timedelta(minutes=6, seconds=30)).to_pydatetime()) == 1
    ref = [json.loads(x) for x in (tmp_path / "senales.jsonl").read_text().splitlines()][-1]
    assert ref["resultado_ref"] == -1 and ref["fuente_ref"] == "resultado oficial de OKX"  # bajaba y subió
