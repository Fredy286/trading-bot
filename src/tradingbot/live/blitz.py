"""Modo de práctica del blitz de BTC de IQ Option (3 min desde la compra, pago 86 %) para cuenta DEMO.

Estudio 42 (pre-registro 78891ce): IQ Option liquida BTC con un promedio de bolsas en USDT, que aquí se reconstruye
como el promedio de los cierres de 1 min de Binance, Bybit y OKX («el compuesto»). En el segundo 50 de cada vela, el
modelo congelado del Estudio 44 decide con las variables de Binance (vela anterior y velas de 1 s hasta el segundo 49)
y tres variables del compuesto. Si la ganancia esperada con el pago del 86 % supera el margen, avisa con sonido; el
blitz empieza con el clic (idealmente al cierre de la vela) y vence 3 min después.

Mismos archivos y reglas que `anticipada` (un archivo, un escritor). La referencia de cada aviso es el resultado con
el compuesto: cierre de la vela del aviso → cierre 3 min después. No envía órdenes a ningún intermediario.

Además, tras cada aviso el bucle graba cada segundo, durante 25 s, el precio de seis bolsas en USDT (`precios.jsonl`).
Con el precio de entrada exacto que el usuario anota de IQ Option, `comparar` mide qué promedio usa la plataforma: el
modelo se entrenó con el de tres bolsas y, con el de cinco, el acierto de octubre bajó de 56,8 % a 54,4 %.
"""

from __future__ import annotations

import hashlib
import json
import pickle
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import requests

from ..research.calibration import Calibrator
from ..research.contracts import BinaryContract
from ..research.experiment import git_sha
from ..research.features import FEATURES, compute_features
from ..research.models import fit_predict_proba
from ..research.study3 import load, spot_bars
from ..research.study16 import minute_table, partial_features
from .. import jsonutil
from ..research.study20 import build_table
from ..execution.paper import read_rows
from ..research.study41 import composite
from ..research.study42 import comp_features, label3
from ..research.study42 import closes as hist_closes
from ..research.study47 import WEIGHTS as IQ_WEIGHTS
from ..research.study47 import iq_price
from ..timeutil import utcnow
from .anticipada import CALIB_FRAC, K, LAT, TRAIN_END, TRAIN_START, SecondsFeed, SignalLoop, download_daily
from .feeds import BinancePollingFeed

PAYOUT, DUR = 0.86, 3
MODEL_PATH = Path("config/modelos/BTCUSDT_blitz3_compuesto.pkl")
REG_PATH = Path("config/senal_blitz.json")
ETH_MODEL_PATH = Path("config/modelos/ETHUSDT_blitz3_compuesto.pkl")  # Estudios 51 y 52
ETH_REG_PATH = Path("config/senal_blitz_eth.json")
MODELOS = {"BTCUSDT": (MODEL_PATH, REG_PATH), "ETHUSDT": (ETH_MODEL_PATH, ETH_REG_PATH)}
CORTO = {"BTCUSDT": "BTC", "ETHUSDT": "ETH"}
NOMBRES = {  # nombre del par en cada bolsa
    "BTCUSDT": {"binance": "BTCUSDT", "bybit": "BTCUSDT", "okx": "BTC-USDT", "gate": "BTC_USDT", "kucoin": "BTC-USDT",
                "bitget": "BTCUSDT"},
    "ETHUSDT": {"binance": "ETHUSDT", "bybit": "ETHUSDT", "okx": "ETH-USDT", "gate": "ETH_USDT", "kucoin": "ETH-USDT",
                "bitget": "ETHUSDT"},
}
HIST_MIN = 70  # cierres que necesitan las variables del compuesto (media de 60 min + 4 + margen)
VENUES = ("bybit", "okx")  # Binance llega por el feed de 1 min de siempre


# ----------------------------------------------------------------------------------------------- entrenamiento
def train_frozen_blitz(root3: Path = Path("data/raw/estudio3"), daily_cache: Path = Path("data/processed/senal/diario"),
                       out: Path | None = None, reg: Path | None = None, log=print, symbol: str = "BTCUSDT") -> dict:
    """Entrena UNA vez el modelo del blitz con los 12 meses hasta el 2026-10-25: BTC (Estudio 42, confirmación en el
    44) o ETH (Estudio 51, confirmación en el 52), con la misma receta."""
    out, reg = Path(out or MODELOS[symbol][0]), Path(reg or MODELOS[symbol][1])
    if out.exists():
        raise FileExistsError(f"{out} ya existe: el modelo se entrena una sola vez (pre-registro).")
    if symbol == "BTCUSDT":
        m_daily = download_daily("1m", "2026-10-01", "2026-10-26", daily_cache)
        spot = pd.concat([load(root3, "BTCUSDT", "spot"), m_daily])
        tab_all = build_table()
        cl = hist_closes("2025-10", "2026-10")
        registro = "Estudio 44 (pre-registro c6ef641): modelo congelado del blitz para la confirmación y la demo"
    elif symbol == "ETHUSDT":
        from ..research import study51

        spot = study51.minute_bars(root3)
        tab_all = pd.read_parquet(study51.TAB)
        cl = {v: x for v, x in study51.closes("2025-10", "2026-10").items() if v in ("binance", "bybit", "okx")}
        registro = "Estudio 52 (pre-registro ad3ce59): modelo congelado del blitz de ETH para la confirmación y la demo"
    else:
        raise ValueError(f"Moneda sin datos para el blitz: {symbol}")
    spot = spot[~spot.index.duplicated(keep="last")].sort_index()
    bars = spot_bars(spot)
    bars = bars[(bars.index >= TRAIN_START - pd.Timedelta(days=3)) & (bars.index < TRAIN_END)]
    idx = bars.index
    tab = tab_all.reindex(idx)
    prev = compute_features(bars).shift(1)
    vol_prev = np.exp(prev["lvol60"])
    comp = composite(cl)
    X = pd.concat([prev[FEATURES], partial_features(tab, bars["o"], vol_prev, K),
                   comp_features(comp, cl["binance"], vol_prev, idx)], axis=1)
    y = label3(comp, idx)
    known = (idx + pd.Timedelta(minutes=DUR + 2)) <= TRAIN_END  # resultado conocido antes del fin
    ok = (idx >= TRAIN_START) & known & X.notna().all(axis=1).to_numpy() & ~np.isnan(y)
    rows = np.flatnonzero(ok)
    cut = idx[rows[int(len(rows) * (1 - CALIB_FRAC))]].floor("D")
    fit = ok & (idx < cut - pd.Timedelta(minutes=DUR + 2)) & (y != 0)  # purga entre ajuste y calibración
    cal = ok & (idx >= cut) & (y != 0)
    model, (pc,) = fit_predict_proba("gbm", X[fit], (y[fit] == 1).astype(int), [X[cal]], seed=2024,
                                     max_rows=400_000, features=list(X.columns))
    calib = Calibrator().fit(pc, (y[cal] == 1).astype(int))
    q = float(np.mean(y[ok & (idx >= cut)] == 0))
    bundle = {"model": model, "calibrator": calib, "features": list(X.columns), "k": K, "latencia": LAT,
              "duracion_min": DUR, "q": q, "train_start": str(TRAIN_START), "train_end": str(TRAIN_END),
              "calib_desde": str(cut), "n_ajuste": int(fit.sum()), "n_calibracion": int(cal.sum()),
              "payout": PAYOUT, "ev_margin": 0.02, "symbol": symbol,
              "precio": f"promedio de Binance, Bybit y OKX ({CORTO[symbol]}/USDT, 1 min)",
              "model_id": f"{symbol}-blitz3-compuesto-{uuid.uuid4().hex[:6]}"}
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    with open(out, "wb") as fh:
        pickle.dump(bundle, fh)
    sha = hashlib.sha256(Path(out).read_bytes()).hexdigest()
    meta = {k: v for k, v in bundle.items() if k not in ("model", "calibrator")}
    meta.update({"model_file": str(out), "model_sha256": sha, "git_sha": git_sha(), "creado": utcnow().isoformat(),
                 "registro": registro})
    Path(reg).write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    log(f"Modelo {bundle['model_id']}: ajuste={fit.sum():,} calibración={cal.sum():,} q={q:.4f} sha256={sha[:12]}…")
    return meta


# ----------------------------------------------------------------------------------------------- decisión
def decide_blitz(bundle: dict, bars: pd.DataFrame, sec: pd.DataFrame, venues: dict[str, pd.Series],
                 minute_open: pd.Timestamp, payout: float | None = None, umbral: float | None = None) -> dict:
    """Decisión en el segundo k de la vela `minute_open`. `bars`: velas de 1 min de Binance CERRADAS; `sec`: velas de
    1 s CERRADAS de la vela en curso; `venues`: cierres de 1 min de Bybit y OKX hasta la vela anterior."""
    t1 = minute_open - pd.Timedelta(minutes=1)
    if bars.index[-1] != t1:
        return {"estado": "sin datos", "motivo": "falta la vela de 1 min anterior de Binance"}
    falta = [v for v in VENUES if venues.get(v) is None or venues[v].empty or venues[v].index[-1] != t1]
    if falta:
        return {"estado": "sin datos", "motivo": f"falta el cierre anterior de {', '.join(falta)}"}
    sec = sec[(sec.index >= minute_open) & (sec.index < minute_open + pd.Timedelta(seconds=bundle["k"]))]
    if sec.empty:
        return {"estado": "sin datos", "motivo": "sin velas de 1 s de la vela en curso"}
    prev = compute_features(bars).iloc[[-1]]
    prev.index = pd.DatetimeIndex([minute_open])
    vol = np.exp(prev["lvol60"])
    tab = minute_table(sec, pd.DatetimeIndex([minute_open]))
    part = partial_features(tab, pd.Series(sec["o"].iloc[0], index=[minute_open]), vol, bundle["k"])
    hist = pd.date_range(minute_open - pd.Timedelta(minutes=HIST_MIN), minute_open, freq="min")
    comp = composite({"binance": bars["c"], **{v: venues[v] for v in VENUES}})
    cf = comp_features(comp, bars["c"], pd.Series(float(vol.iloc[0]), index=hist), hist).iloc[[-1]]
    X = pd.concat([prev[FEATURES], part, cf], axis=1)[bundle["features"]]
    if X.isna().any(axis=1).iloc[0]:
        return {"estado": "sin datos", "motivo": "variables incompletas (faltan segundos o historia)"}
    p_up = float(bundle["calibrator"].transform(bundle["model"].predict_proba(X.to_numpy())[:, 1])[0])
    side = 1 if p_up >= 0.5 else -1
    p_dir = p_up if side == 1 else 1 - p_up
    b = bundle["payout"] if payout is None else payout
    ev = float(BinaryContract(b, "refund").ev(np.array([p_dir]), np.array([bundle["q"]]))[0])
    fires = ev >= bundle["ev_margin"] and (umbral is None or p_dir >= umbral)
    return {"estado": "señal" if fires else "sin señal", "lado": side, "p": p_dir, "ev": ev,
            "compuesto": float(comp.loc[t1])}


def _resultado(o: float, e: float, lado: int) -> int:
    """+1 gana, −1 pierde, 0 empate, con la regla de `label3` (empate si |salida − entrada| < 0,005). Antes se usaba
    round(d / 0,005), que con promedios (pasos de 1/300 o con pesos) contaba como gana/pierde lo que el estudio
    trata como empate (registro de errores 51)."""
    d = e - o
    return 0 if abs(d) < 0.005 else int(np.sign(d)) * int(lado)


# ----------------------------------------------------------------------------------------------- datos en vivo
def _ms(t: pd.Timestamp) -> int:
    return int(t.timestamp() * 1000)


# Las mismas peticiones del Estudio 41, pero con un solo intento y 5 s de espera: en vivo no se puede bloquear el bucle
# (el Estudio 41 reintenta hasta seis veces). Ventanas de ≤ 100 min (tope de OKX por petición).
def requests_for(symbol: str = "BTCUSDT") -> dict:
    n = NOMBRES[symbol]
    return {
        "binance": ("https://api.binance.com/api/v3/klines",
                    lambda a, b: {"symbol": n["binance"], "interval": "1m", "startTime": _ms(a), "endTime": _ms(b),
                                  "limit": 100},
                    lambda j: [(int(x[0]), float(x[4])) for x in j]),
        "bybit": ("https://api.bybit.com/v5/market/kline",
                  lambda a, b: {"category": "spot", "symbol": n["bybit"], "interval": "1", "start": _ms(a),
                                "end": _ms(b), "limit": 100},
                  lambda j: [(int(x[0]), float(x[4])) for x in j["result"]["list"]]),
        "okx": ("https://www.okx.com/api/v5/market/history-candles",
                lambda a, b: {"instId": n["okx"], "bar": "1m", "after": _ms(b) + 1, "before": _ms(a) - 1, "limit": 100},
                lambda j: [(int(x[0]), float(x[4])) for x in j["data"] if len(x) < 9 or x[8] == "1"]),
        # Gate: solo para la referencia con el precio IQ reconstruido (Estudio 47); su API guarda ~7 días
        "gate": ("https://api.gateio.ws/api/v4/spot/candlesticks",
                 lambda a, b: {"currency_pair": n["gate"], "interval": "1m", "from": int(a.timestamp()),
                               "to": int(b.timestamp())},
                 lambda j: [(int(x[0]) * 1000, float(x[2])) for x in j]),
    }


REQUESTS = requests_for("BTCUSDT")


class UsdtCloses:
    """Cierres de 1 min ya cerrados de una moneda en USDT en Binance, Bybit, OKX y Gate (API públicas, sin
    credenciales)."""

    def __init__(self, session=None, symbol: str = "BTCUSDT"):
        self.session = session or requests.Session()
        self.symbol = symbol
        self.requests = requests_for(symbol)

    def get(self, venue: str, a: pd.Timestamp, b: pd.Timestamp) -> pd.Series:
        url, params, parse = self.requests[venue]
        r = self.session.get(url, params=params(a, b), timeout=5)
        r.raise_for_status()
        s = pd.Series({pd.Timestamp(t, unit="ms", tz="UTC"): c for t, c in parse(r.json())}, dtype=float).sort_index()
        return s[(s.index >= a) & (s.index <= b)]

    def recent(self, t1: pd.Timestamp, n: int = HIST_MIN + 5) -> dict[str, pd.Series]:
        a = t1 - pd.Timedelta(minutes=n - 1)
        return {v: self.get(v, a, t1) for v in VENUES}


# ----------------------------------------------------------------------------------------------- grabador de precios
def _mid(b, a):
    return (float(b) + float(a)) / 2


# bolsa → (url, parámetros, lectura → (último, medio)); Binance no da el último en esta respuesta (su diferencial es
# de 0,01, así que el medio sirve igual)
def tickers_for(symbol: str = "BTCUSDT") -> dict:
    n = NOMBRES[symbol]
    return {
        "binance": ("https://api.binance.com/api/v3/ticker/bookTicker", {"symbol": n["binance"]},
                    lambda j: (None, _mid(j["bidPrice"], j["askPrice"]))),
        "bybit": ("https://api.bybit.com/v5/market/tickers", {"category": "spot", "symbol": n["bybit"]},
                  lambda j: (lambda x: (float(x["lastPrice"]), _mid(x["bid1Price"], x["ask1Price"])))(j["result"]["list"][0])),
        "okx": ("https://www.okx.com/api/v5/market/ticker", {"instId": n["okx"]},
                lambda j: (lambda x: (float(x["last"]), _mid(x["bidPx"], x["askPx"])))(j["data"][0])),
        "kucoin": ("https://api.kucoin.com/api/v1/market/orderbook/level1", {"symbol": n["kucoin"]},
                   lambda j: (float(j["data"]["price"]), _mid(j["data"]["bestBid"], j["data"]["bestAsk"]))),
        "bitget": ("https://api.bitget.com/api/v2/spot/market/tickers", {"symbol": n["bitget"]},
                   lambda j: (lambda x: (float(x["lastPr"]), _mid(x["bidPr"], x["askPr"])))(j["data"][0])),
        "gate": ("https://api.gateio.ws/api/v4/spot/tickers", {"currency_pair": n["gate"]},
                 lambda j: (float(j[0]["last"]), _mid(j[0]["highest_bid"], j[0]["lowest_ask"]))),
    }


TICKERS = tickers_for("BTCUSDT")
IQ_NAME = "IQ reconstruido (pesos del Estudio 47)"
# promedios candidatos para el precio de IQ Option (precio medio de cada bolsa)
CANDIDATOS = {"Binance sola": ("binance",), "OKX sola": ("okx",), "3 bolsas (Binance, Bybit, OKX)": ("binance", "bybit", "okx"),
              "5 bolsas (+ KuCoin, Bitget)": ("binance", "bybit", "okx", "kucoin", "bitget"),
              "6 bolsas (+ Gate)": ("binance", "bybit", "okx", "kucoin", "bitget", "gate")}


class PriceRecorder:
    """Graba cada segundo el precio de las seis bolsas durante unos segundos tras un aviso (hilo aparte; si una bolsa
    no responde, esa fila la deja vacía). Escribe solo `precios.jsonl`."""

    def __init__(self, path: Path, clock, session=None, seconds: int = 25, symbol: str = "BTCUSDT"):
        self.path, self.clock, self.seconds = Path(path), clock, seconds
        self.session = session or requests.Session()
        self.tickers = tickers_for(symbol)
        self.pool = ThreadPoolExecutor(max_workers=len(self.tickers))

    def _one(self, venue: str):
        url, params, parse = self.tickers[venue]
        try:
            r = self.session.get(url, params=params, timeout=2)
            r.raise_for_status()
            last, mid = parse(r.json())
            return {"ultimo": last, "medio": mid}
        except (requests.RequestException, ValueError, KeyError, IndexError, TypeError):
            return None

    def snapshot(self) -> dict:
        t0 = pd.Timestamp(self.clock())
        got = dict(zip(self.tickers, self.pool.map(self._one, self.tickers)))
        t1 = pd.Timestamp(self.clock())
        return {"t": (t0 + (t1 - t0) / 2).isoformat(), "duracion_s": round((t1 - t0).total_seconds(), 3), **got}

    def record(self, alert_id: str) -> None:
        end = time.monotonic() + self.seconds
        while time.monotonic() < end:
            start = time.monotonic()
            jsonutil.append_line(self.path, jsonutil.dumps({"alert_id": alert_id, **self.snapshot()}))
            time.sleep(max(0.0, 1.0 - (time.monotonic() - start)))

    def start(self, alert_id: str) -> threading.Thread:
        th = threading.Thread(target=self.record, args=(alert_id,), daemon=True)
        th.start()
        return th


def comparar(runtime: Path, max_gap_s: float = 2.0) -> dict:
    """Para cada operación con clic y precio de entrada anotado de la plataforma, el error de cada promedio candidato
    en el segundo grabado más cercano al clic. El promedio con menor error es el que usa la plataforma."""
    d = Path(runtime)
    clics = {}
    for c in read_rows(d / "clics.jsonl")[0]:
        clics.setdefault(c.get("alert_id"), c)
    entradas = {}
    for g in read_rows(d / "registros.jsonl")[0]:
        if g.get("entrada") not in (None, ""):
            entradas[g["alert_id"]] = float(g["entrada"])
    precios: dict[str, list] = {}
    for p in read_rows(d / "precios.jsonl")[0]:
        precios.setdefault(p.get("alert_id"), []).append(p)
    filas = []
    for aid, entrada in entradas.items():
        c, rows = clics.get(aid), precios.get(aid)
        if not c or not c.get("hora_binance") or not rows:
            continue
        t = pd.Timestamp(c["hora_binance"])
        best = min(rows, key=lambda p: abs((pd.Timestamp(p["t"]) - t).total_seconds()))
        gap = abs((pd.Timestamp(best["t"]) - t).total_seconds())
        if gap > max_gap_s:
            continue
        fila = {"alert_id": aid, "clic": c["hora_binance"], "entrada_plataforma": entrada, "desfase_s": gap}
        for name, venues in CANDIDATOS.items():
            vals = [best[v]["medio"] for v in venues if best.get(v)]
            fila[name] = entrada - float(np.mean(vals)) if len(vals) == len(venues) else None
        ok = all(best.get(v) for v in IQ_WEIGHTS)  # la mezcla con pesos del Estudio 47
        fila[IQ_NAME] = (entrada - sum(best[v]["medio"] * w for v, w in IQ_WEIGHTS.items()) / sum(IQ_WEIGHTS.values())
                         if ok else None)
        filas.append(fila)
    resumen = {}
    for name in [*CANDIDATOS, IQ_NAME]:
        e = np.array([f[name] for f in filas if f[name] is not None], float)
        resumen[name] = {"n": int(len(e)), "error_medio": float(e.mean()) if len(e) else None,
                         "error_cuadratico": float(np.sqrt((e ** 2).mean())) if len(e) else None}
    return {"operaciones": len(filas), "candidatos": resumen, "filas": filas}


# ----------------------------------------------------------------------------------------------- bucle
class BlitzLoop(SignalLoop):
    """Una decisión por minuto (segundo 50) para cada moneda vigilada. Si varias dan señal en el mismo minuto, avisa
    solo la de mayor probabilidad (una operación a la vez) y anota las demás en el aviso."""

    def __init__(self, bundle: dict, runtime: Path, feed=None, secfeed=None, venues=None, sound: bool = True,
                 log=print, pago: float | None = None, umbral: float | None = None, record: bool = True, telegram=None,
                 extra: list[dict] | None = None):
        super().__init__(bundle, runtime, feed=feed, secfeed=secfeed, sound=sound, log=log, pago=pago, umbral=umbral,
                         telegram=telegram)
        self.venues = venues or UsdtCloses(self.feed.session)
        self.assets = [{"symbol": bundle.get("symbol", "BTCUSDT"), "bundle": bundle, "feed": self.feed,
                        "sec": self.sec, "venues": self.venues}]
        for x in extra or []:  # otras monedas: {"symbol", "bundle"} y, en pruebas, sus propios feed/sec/venues
            sym = x["symbol"]
            f = x.get("feed") or BinancePollingFeed(sym)
            self.assets.append({"symbol": sym, "bundle": x["bundle"], "feed": f,
                                "sec": x.get("sec") or SecondsFeed(f.session, symbol=sym),
                                "venues": x.get("venues") or UsdtCloses(f.session, symbol=sym)})
        self.by_symbol = {a["symbol"]: a for a in self.assets}
        self.extra_state = {"modo": "blitz", "duracion_min": DUR, "precio": bundle.get("precio"),
                            "activos": [CORTO.get(a["symbol"], a["symbol"]) for a in self.assets]}
        self.record = record
        self.recorders: dict[str, PriceRecorder] = {}
        self.pool = ThreadPoolExecutor(max_workers=max(1, len(self.assets)))

    def _decide(self, a: dict, now: datetime, minute_open: pd.Timestamp) -> dict:
        try:
            bars, _ = a["feed"].get(now)
            sec = a["sec"].get(minute_open, now)
            venues = a["venues"].recent(minute_open - pd.Timedelta(minutes=1))
            d = decide_blitz(a["bundle"], bars, sec, venues, minute_open, self.pago, self.umbral)
        except (requests.RequestException, ValueError, KeyError) as exc:
            if len(self.assets) == 1:
                raise  # una sola moneda: el bucle informa el error como siempre
            d = {"estado": "error", "motivo": f"{type(exc).__name__}: {exc}"[:200]}
        d.update({"activo": CORTO.get(a["symbol"], a["symbol"]), "symbol": a["symbol"],
                  "model_id": a["bundle"]["model_id"]})
        return d

    def step(self, now: datetime) -> dict:
        minute_open = pd.Timestamp(now).floor("min")
        if len(self.assets) == 1:
            decisions = [self._decide(self.assets[0], now, minute_open)]
        else:  # en paralelo: el aviso no debe llegar más tarde por vigilar más monedas
            decisions = list(self.pool.map(lambda a: self._decide(a, now, minute_open), self.assets))
        self.n_minutes += 1
        signals = sorted((x for x in decisions if x["estado"] == "señal"), key=lambda x: -x["p"])
        d = signals[0] if signals else next((x for x in decisions if x["estado"] != "error"), decisions[0])
        d.update({"vela": minute_open.isoformat(), "decidido": pd.Timestamp(now).isoformat(),
                  "cierre": (minute_open + pd.Timedelta(minutes=1)).isoformat(),
                  "vence": (minute_open + pd.Timedelta(minutes=1 + DUR)).isoformat()})
        if len(self.assets) > 1:
            d["otras"] = [{"activo": x["activo"], "estado": x["estado"], "lado": x.get("lado"), "p": x.get("p")}
                          for x in decisions if x is not d]
        if d["estado"] == "señal":
            self.n_signals += 1
            d["alert_id"] = uuid.uuid4().hex[:12]
            d["emitido"] = pd.Timestamp(self.feed.server_now()).isoformat()
            self._write({"evento": "aviso", **d})
            self._beep()
            self._notify(d)
            if self.record:  # precios de las seis bolsas mientras el usuario hace clic
                sym = d["symbol"]
                if sym not in self.recorders:
                    self.recorders[sym] = PriceRecorder(self.dir / "precios.jsonl", self.feed.server_now, symbol=sym)
                self.recorders[sym].start(d["alert_id"])
        self.last = d
        return d

    def fill_references(self, now: datetime) -> int:
        """Resultado de cada aviso con el compuesto: cierre de la vela del aviso → cierre 3 min después (lo que
        mide el Estudio 42), en cuanto las tres bolsas publican la vela del vencimiento."""
        done = 0
        for a in read_rows(self.dir / "senales.jsonl")[0]:
            aid = a.get("alert_id")
            if a.get("evento") != "aviso" or aid in self.referenced:
                continue
            t = pd.Timestamp(a["vela"])
            end = t + pd.Timedelta(minutes=DUR)
            if pd.Timestamp(now) < end + pd.Timedelta(seconds=80):  # la vela t + 3 cierra en t + 4 min
                continue
            sym = a.get("symbol", "BTCUSDT")
            src = self.by_symbol[sym]["venues"] if sym in self.by_symbol else UsdtCloses(self.feed.session, symbol=sym)
            closes = {v: src.get(v, t, end) for v in VENUES}
            closes["binance"] = src.get("binance", t, end)
            o, e = (lambda c: (c.get(t), c.get(end)))(composite(closes))
            res = None if o is None or e is None else _resultado(o, e, a["lado"])
            row = {"evento": "referencia", "alert_id": aid, "entrada_ref": o, "salida_ref": e, "resultado_ref": res,
                   "fuente_ref": "promedio de Binance, Bybit y OKX"}
            try:  # además, con el precio IQ reconstruido (Estudio 47): mismo juicio, otra mezcla
                iq = iq_price({**closes, "gate": src.get("gate", t, end)})
                oi, ei = iq.get(t), iq.get(end)
                row["resultado_iq"] = None if oi is None or ei is None else _resultado(oi, ei, a["lado"])
            except (requests.RequestException, ValueError, KeyError):
                row["resultado_iq"] = None
            self._write(row)
            self.referenced.add(aid)
            done += 1
        return done
