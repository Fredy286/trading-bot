"""Modo de práctica del gran bot (idea 7 de docs/10): mismas reglas y mismas opiniones que el registro diario."""

import json

import numpy as np
import pandas as pd
import pytest

from tradingbot.data import synthetic
from tradingbot.data.clean import to_canonical
from tradingbot.live import gran_bot as gb
from tradingbot.live import gran_vivo as gv
from tradingbot.live import okx_eventos as ok
from tradingbot.live.anticipada import aviso_texto, load_bundle
from tradingbot.research.features import FEATURES, compute_features
from tradingbot.research.study16 import minute_table, partial_features
from tradingbot.research.study41 import composite
from tradingbot.research.study42 import comp_features

RNG = np.random.default_rng(7)


def _op(n):
    """Opiniones al azar con todas las claves que usan los tres metamodelos."""
    return [{k: float(RNG.uniform(0.35, 0.65)) for k in gv.MONEDA_DE} for _ in range(n)]


@pytest.mark.parametrize("dur", [5, 15])
def test_okx_rule_is_the_daily_registry_rule(dur):
    cfg, gid = gv.cargar(f"okx{dur}")
    assert gid.startswith(f"gran-okx{dur}-")
    t = pd.date_range("2026-11-05 03:14", periods=40, freq=f"{dur}min", tz="UTC")
    ops = _op(len(t))
    op = pd.DataFrame(ops, index=t)
    filas = (gb.filas_dia if dur == 5 else gb.filas_15)(op, cfg["coeficientes"], {})
    assert len(filas) == 2 * len(t)
    vistos = 0
    for f in filas:
        i = t.get_loc(pd.Timestamp(f["ventana"]) - pd.Timedelta(minutes=1))
        d = gv.decidir_okx({"opiniones": ops[i], "faltan": []}, cfg["coeficientes"][f["moneda"]], f["moneda"], dur)
        assert d["p_gran"] == pytest.approx(f["p_gran"], abs=1e-5)
        assert (d["estado"] == "señal") == f["senal_gran"] and d["senal_base"] == f["senal_base"]
        assert d["opiniones"] == f["opiniones"] and d["p_base"] == pytest.approx(f["p_base"], abs=1e-5)
        vistos += d["estado"] == "señal"
    assert 0 < vistos < len(filas)  # la prueba cubre los dos casos


def test_blitz_rule_is_the_daily_registry_rule():
    cfg, _ = gv.cargar("blitz")
    q = float(load_bundle(*gb.bases()["p42"])["q"])
    t = pd.date_range("2026-11-05 03:00", periods=300, freq="min", tz="UTC")
    ops = _op(len(t))
    filas = {f["vela"]: f for f in gb.filas_blitz(pd.DataFrame(ops, index=t), cfg["coeficientes"], q,
                                                   pd.Series(np.nan, index=t))}
    assert 0 < len(filas) < len(t)
    for x, op in zip(t, ops):
        d = gv.decidir_blitz({"opiniones": op, "faltan": [], "compuesto": {}}, cfg["coeficientes"], q, cfg["pago"],
                             cfg["margen"])
        f = filas.get(x.isoformat())
        if f is None:  # el registro solo guarda las velas con aviso del gran bot o de la base
            assert d["estado"] == "sin señal" and not d["senal_base"]
            continue
        assert d["p_gran"] == pytest.approx(f["p_gran"], abs=1e-5) and d["opiniones"] == f["opiniones"]
        assert (d["estado"] == "señal") == f["senal_gran"] and d["senal_base"] == f["senal_base"]


def test_missing_opinions_mean_no_signal():
    cfg, _ = gv.cargar("okx5")
    op = _op(1)[0]
    del op["p53"]
    d = gv.decidir_okx({"opiniones": op, "faltan": ["SOL: falta el cierre anterior de okx"]},
                       cfg["coeficientes"]["ETHUSDT"], "ETHUSDT", 5)
    assert d["estado"] == "sin datos" and "SOL" in d["motivo"]


# ----------------------------------------------------------------------------------------------- opiniones en vivo
@pytest.fixture(scope="module")
def mercado():
    """Velas sintéticas distintas para cada moneda, segundos del minuto t y cierres de Bybit y OKX."""
    out = {}
    for i, s in enumerate(gv.ORDEN):
        bars, _ = to_canonical(synthetic.generate(start="2024-01-01", days=3, phi=0.0, seed=10 + i))
        bars = bars * (1 + i)  # niveles de precio distintos
        out[s] = bars
    t = out["BTCUSDT"].index[-30]
    secs = {}
    for i, s in enumerate(gv.ORDEN):
        idx = pd.date_range(t, periods=60, freq="s")
        c = out[s].loc[t, "o"] * np.exp(np.cumsum(np.random.default_rng(i).normal(0, 2e-5, 60)))
        o = np.r_[out[s].loc[t, "o"], c[:-1]]
        secs[s] = pd.DataFrame({"o": o, "h": np.maximum(o, c) * (1 + 1e-6), "l": np.minimum(o, c) * (1 - 1e-6),
                                "c": c, "v": 1.0 + i, "tb": 0.6, "n": 2.0}, index=idx)
    ven = {s: {"bybit": out[s]["c"] * (1 - 1e-4), "okx": out[s]["c"] * (1 + 5e-5)} for s in gv.COMPUESTO}
    return out, secs, ven, t


def _fuentes(mercado, now, cuenta=None):
    out, secs, ven, t = mercado
    cuenta = {} if cuenta is None else cuenta

    class _Feed:
        offset_s, session = 0.0, None

        def __init__(self, s):
            self.s = s

        def get(self, now=None):
            cuenta[self.s] = cuenta.get(self.s, 0) + 1
            b = out[self.s]
            return b[b.index < t].iloc[-2000:], now

        def server_now(self):
            return now

    class _Sec:
        def __init__(self, s):
            self.s = s

        def get(self, start, now, limit=120):
            return secs[self.s][secs[self.s].index < pd.Timestamp(now).floor("s")]

    class _V:
        def __init__(self, s):
            self.s = s

        def recent(self, t1, n=75):
            return {v: x[(x.index <= t1)].iloc[-n:] for v, x in ven[self.s].items()}

    return {s: {"feed": _Feed(s), "sec": _Sec(s), **({"venues": _V(s)} if s in gv.COMPUESTO else {})}
            for s in gv.ORDEN}


def _por_lotes(mercado, bundles):
    """Las opiniones con el camino del registro diario (`gran_bot.opiniones_dia`): todo el día de una vez."""
    out, secs, ven, t = mercado
    res = {}
    for k, b in bundles.items():
        s = gv.MONEDA_DE[k]
        bars = out[s]
        prev = compute_features(bars).shift(1)
        vol = np.exp(prev["lvol60"])
        tab = minute_table(secs[s], pd.DatetimeIndex([t])).reindex(bars.index)
        partes = [prev[FEATURES], partial_features(tab, bars["o"], vol, 50)]
        if s in gv.COMPUESTO:
            comp = composite({"binance": bars["c"], **ven[s]})
            partes.append(comp_features(comp, bars["c"], vol, bars.index))
        X = pd.concat(partes, axis=1)
        X = X.loc[:, ~X.columns.duplicated()]
        res[k] = float(gb._probas(b, X, np.asarray(bars.index == t), bars.index).loc[t])
    return res


def test_live_opinions_equal_the_registry_batch_path(mercado):
    """Cada opinión sale de los datos de SU moneda y con las mismas variables que el registro diario."""
    t = mercado[3]
    now = (t + pd.Timedelta(seconds=50.3)).to_pydatetime()
    claves = sorted(gv.MONEDA_DE)
    todo = {**gb.bases(), **gb.bases_extra()}
    bundles = {k: load_bundle(*todo[k]) for k in claves}
    op = gv.Opinador(claves, fuentes=_fuentes(mercado, now), bundles=bundles)
    r = op.opinar(now, t)
    assert not r["faltan"] and set(r["opiniones"]) == set(claves)
    lotes = _por_lotes(mercado, bundles)
    for k in claves:
        assert r["opiniones"][k] == pytest.approx(lotes[k], abs=1e-9), k
    assert len({round(v, 6) for v in r["opiniones"].values()}) > 6  # opiniones distintas: no se cruzaron monedas
    assert op.opinar(now, t) is r  # una sola vez por vela
    # preparado en el segundo 35: mismas opiniones y, en el segundo 50, ya no se piden velas de 1 min
    cuenta = {}
    prep = gv.Opinador(claves, fuentes=_fuentes(mercado, now, cuenta), bundles=bundles)
    prep.preparar((t + pd.Timedelta(seconds=35)).to_pydatetime(), t)
    assert cuenta == {s: 1 for s in gv.ORDEN}
    r2 = prep.opinar(now, t)
    assert r2["preparado"] and cuenta == {s: 1 for s in gv.ORDEN}
    assert r2["opiniones"] == pytest.approx(r["opiniones"], abs=1e-12)
    # una preparación de otra vela no sirve: se baja todo de nuevo
    otra = gv.Opinador(claves, fuentes=_fuentes(mercado, now, cuenta := {}), bundles=bundles)
    otra.preparar(now, t - pd.Timedelta(minutes=1))
    assert not otra.opinar(now, t)["preparado"]


# ----------------------------------------------------------------------------------------------- bucles
class _Opinador:
    """Opiniones fijas (sin red) con los modelos de verdad para la base y la cuenta del bucle."""

    def __init__(self, claves, valores):
        todo = {**gb.bases(), **gb.bases_extra()}
        self.bundles = {k: load_bundle(*todo[k]) for k in claves}
        self.valores, self.llamadas = valores, 0

    def opinar(self, now, minute_open):
        self.llamadas += 1
        return {"opiniones": dict(self.valores), "faltan": [], "compuesto": {"BTCUSDT": 100.0}}

    def precargar(self, now):
        pass


class _Feed:
    offset_s, session = 0.0, None

    def __init__(self, now):
        self.now = now

    def get(self, now=None):
        return None, now

    def server_now(self):
        return self.now


def test_blitz_loop_alerts_with_the_frozen_metamodel_and_respects_iq_hours(tmp_path):
    minute = pd.Timestamp("2026-11-18 03:10", tz="UTC")  # miércoles, IQ abierto
    now = (minute + pd.Timedelta(seconds=50.3)).to_pydatetime()
    claves = gv.PRODUCTOS["blitz"]["claves"]
    fuerte = {k: 0.62 for k in claves}  # todas dicen «sube»
    op = _Opinador(claves, fuerte)
    loop = gv.GranBlitzLoop(tmp_path, sound=False, record=False, opinador=op, feed=_Feed(now), secfeed=object(),
                            venues=object(), horario={"zona": "UTC", "abre": {"dia": 0, "hora": "00:00"},
                                                      "cierra": {"dia": 6, "hora": "23:59"}, "pausas": []})
    d = loop.step(now)
    assert d["estado"] == "señal" and d["lado"] == 1 and d["gran"] and d["model_id"].startswith("gran-blitz-")
    assert d["vence"] == (minute + pd.Timedelta(minutes=4)).isoformat()
    rows = [json.loads(x) for x in (tmp_path / "senales.jsonl").read_text().splitlines()]
    assert len(rows) == 1 and rows[0]["opiniones"]["propia"] == 0.62 and rows[0]["p_gran"] > 0.62
    assert aviso_texto(d, "blitz").startswith("🔔 Gran bot · BTC blitz 3 min: ↑ SUBE")
    loop.write_state(now)
    st = json.loads((tmp_path / "state.json").read_text())
    assert st["gran"] and st["producto"] == "blitz" and st["model_id"] == loop.gran_id
    nunca = {"zona": "UTC", "abre": {"dia": 6, "hora": "23:59"}, "cierra": {"dia": 6, "hora": "23:59"}, "pausas": []}
    cerrado = gv.GranBlitzLoop(tmp_path / "c", sound=False, record=False, opinador=op, feed=_Feed(now),
                               secfeed=object(), venues=object(), horario=nunca)
    x = cerrado.step(now)
    assert x["estado"] == "cerrado" and x["senal_modelo"]
    assert not (tmp_path / "c" / "senales.jsonl").exists()


class _Eventos(ok.OkxEventos):
    def __init__(self, ask=0.51, bid=0.49, cant=13.1):
        super().__init__(session=object())
        self.ask, self.bid, self.cant, self.pedidos = ask, bid, cant, []

    def libro(self, inst, niveles=5):
        self.pedidos.append(inst)
        return {"a": [[self.ask, self.cant]], "b": [[self.bid, self.cant]]}

    def resultado(self, symbol, inst, after_ms=None, dur=5):
        self.pedidos.append((inst, dur))
        return {"outcome": "1", "partida": 100.0, "liquidacion": 101.0}


@pytest.mark.parametrize("dur", [5, 15])
def test_okx_loop_uses_one_opinion_set_for_both_coins_and_the_right_contract(tmp_path, dur):
    claves = gv.PRODUCTOS[f"okx{dur}"]["claves"]
    valores = {k: 0.60 for k in claves}  # todas dicen «sube»
    op = _Opinador(claves, valores)
    grid = pd.Timestamp("2026-11-18 03:14", tz="UTC") if dur == 5 else pd.Timestamp("2026-11-18 03:29", tz="UTC")
    now = (grid + pd.Timedelta(seconds=50.3)).to_pydatetime()
    ev = _Eventos()
    fuentes = {s: {"feed": _Feed(now), "sec": object(), "venues": object()} for s in ("ETHUSDT", "BTCUSDT")}
    loop = gv.GranOkxLoop(tmp_path, dur=dur, sound=False, eventos=ev, opinador=op, fuentes=fuentes)
    antes = (grid - pd.Timedelta(minutes=1) + pd.Timedelta(seconds=50.3)).to_pydatetime()
    assert loop.step(antes)["estado"] == "fuera de turno" and op.llamadas == 0
    d = loop.step(now)
    ventana = grid + pd.Timedelta(minutes=1)
    assert d["estado"] == "señal" and d["gran"] and d["model_id"].startswith(f"gran-okx{dur}-")
    assert d["instrumento"] == ok.inst_id(d["symbol"], ventana, dur) and f"-UPDOWN-{dur}MIN-" in d["instrumento"]
    assert d["vence"] == (ventana + pd.Timedelta(minutes=dur)).isoformat()
    assert d["otras"][0]["estado"] == "señal"  # la otra moneda también, con las mismas opiniones
    assert op.llamadas == 2 and len(ev.pedidos) == 2  # el libro de cada moneda
    texto = aviso_texto(d, "okx")
    fin = (ventana + pd.Timedelta(minutes=dur)).tz_convert("America/Bogota")
    assert texto.startswith(f"🔔 Gran bot · OKX {d['activo']} {dur} min: ↑ SUBE")
    assert f"pestaña «{fin:%H:%M}»" in texto
    later = (ventana + pd.Timedelta(minutes=dur, seconds=30)).to_pydatetime()
    assert loop.fill_references(later) == 1 and ev.pedidos[-1] == (d["instrumento"], dur)


def test_panel_serves_the_gran_pages_from_their_own_folders(tmp_path):
    import threading
    import urllib.request

    from tradingbot.app.server import make_server

    carpetas = {m: tmp_path / m for m in ("gran-blitz", "gran-okx5", "gran-okx15")}
    for m, c in carpetas.items():
        c.mkdir()
        (c / "state.json").write_text(json.dumps({"minutos": 3, "avisos": 0, "producto": m}), encoding="utf-8")
    srv = make_server("127.0.0.1", 0, tmp_path / "demo", tmp_path / "res", gran_dirs=carpetas)
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    try:
        port = srv.server_address[1]
        for m in carpetas:
            html = urllib.request.urlopen(f"http://127.0.0.1:{port}/{m}").read().decode()
            assert "GRAN_BANNER" in html
            st = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{port}/api/{m}/state").read())
            assert st["producto"] == m and st["resumen"]["avisos"] == 0
    finally:
        srv.shutdown()
