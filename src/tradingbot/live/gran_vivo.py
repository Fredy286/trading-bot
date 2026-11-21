"""Modo de práctica del «gran bot» (idea 7 de docs/10): junta en vivo los modelos congelados y sus metamodelos.

Tres productos, cada uno con su metamodelo congelado (no se ajusta nada aquí):
- `okx5`: contratos de 5 min de OKX, ETH y BTC, 6 opiniones (Estudio 63; metamodelo del Estudio 64,
  `config/gran_bot_okx5.json`);
- `okx15`: contratos de 15 min de OKX, ETH y BTC, 8 opiniones (Estudio 67; `config/gran_bot_okx15.json`, Estudio 69);
- `blitz`: blitz de BTC de IQ Option (3 min, pago 86 %), 8 opiniones (Estudio 66; `config/gran_bot_blitz.json`,
  Estudio 68). Solo avisa con IQ Option abierto (`config/horario_iq_blitz.json`).

En el segundo 50 de cada vela de decisión, `Opinador` baja en paralelo los datos de cada moneda que hace falta (vela de
1 min anterior de Binance, velas de 1 s hasta el segundo 49 y, para BTC, ETH y SOL, los cierres de Bybit y OKX del
compuesto), calcula la opinión de cada modelo congelado con las MISMAS funciones que los modos de práctica de siempre
(`blitz.previas_blitz`, `anticipada.previas_binance` y `anticipada.con_segundos`) y el metamodelo las combina con la
fórmula del registro diario (`gran_bot._combinar_con`). La regla de aviso es la del registro (`gran_bot.filas_dia`,
`filas_15`, `filas_blitz`). Para que el aviso salga enseguida, en el segundo 35 un hilo prepara lo que solo depende de
velas cerradas (`Opinador.preparar`); en el segundo 50 solo faltan las velas de 1 s del minuto en curso.

Comprobado con datos reales (2026-11-19, 200–408 minutos): las 12 opiniones coinciden con `gran_bot.opiniones_dia` y la
probabilidad final con la que guardó el registro de la nube (≤ 0,000005); la de SOL de 1 min difiere en contados minutos
porque el registro guarda los volúmenes de 1 s en float32 (registro de errores 61).

Los bucles heredan de los modos OKX y blitz: mismo panel, sonido, Telegram, clic, diario y referencia. No envían órdenes
a ningún intermediario. Las confirmaciones (Estudios 64, 68 y 69) se juzgan con el registro diario sellado, no con esto.
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import requests

from ..research import study63
from ..research.contracts import BinaryContract
from . import gran_bot as gb
from .anticipada import SecondsFeed, con_segundos, load_bundle, previas_binance
from .blitz import CORTO, BlitzLoop, UsdtCloses, previas_blitz
from .feeds import BinancePollingFeed
from .okx_eventos import PRECIO_MAX, OkxEventos, OkxLoop, modelos

K = 50  # todas las opiniones deciden en el segundo 50 (lo exige `gran_bot.opiniones_dia`)
ORDEN = ("BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT")
COMPUESTO = ("BTCUSDT", "ETHUSDT", "SOLUSDT")  # con el compuesto de Binance, Bybit y OKX; XRP y DOGE, solo Binance
MONEDA_DE = {"okx5_ETHUSDT": "ETHUSDT", "okx5_BTCUSDT": "BTCUSDT", "okx15_ETHUSDT": "ETHUSDT",
             "okx15_BTCUSDT": "BTCUSDT", "p20": "BTCUSDT", "p42": "BTCUSDT", "p51": "ETHUSDT", "p53": "SOLUSDT",
             "e26_eth": "ETHUSDT", "e26_sol": "SOLUSDT", "e26_xrp": "XRPUSDT", "e26_doge": "DOGEUSDT"}
PRODUCTOS = {
    "okx5": {"config": gb.CONFIG, "dur": 5, "estudios": "Estudios 63 y 64",
             "claves": ("okx5_ETHUSDT", "okx5_BTCUSDT", "p20", "p42", "p51", "p53")},
    "okx15": {"config": gb.CONFIG_15, "dur": 15, "estudios": "Estudios 67 y 69",
              "claves": ("okx15_ETHUSDT", "okx15_BTCUSDT", "okx5_ETHUSDT", "okx5_BTCUSDT", "p20", "p42", "p51", "p53")},
    "blitz": {"config": gb.CONFIG_BLITZ, "dur": 3, "estudios": "Estudios 66 y 68",
              "claves": ("p42", "p51", "p53", "p20", "e26_eth", "e26_sol", "e26_xrp", "e26_doge")},
}


def cargar(producto: str) -> tuple[dict, str]:
    """Metamodelo congelado del producto y su identificador (primeros 12 del SHA-256 del archivo). Comprueba que cada
    modelo base sea EXACTAMENTE el que se usó al congelarlo (mismo SHA-256 en su registro)."""
    cfg_path = PRODUCTOS[producto]["config"]
    raw = Path(cfg_path).read_bytes()
    cfg = json.loads(raw)
    todo = {**gb.bases(), **gb.bases_extra()}
    for k, info in cfg["bases"].items():
        reg = json.loads(Path(todo[k][1]).read_text(encoding="utf-8"))
        if reg["model_sha256"] != info["model_sha256"]:
            raise ValueError(f"{k}: el modelo registrado no es el que usó el metamodelo de {cfg_path}")
    return cfg, f"gran-{producto}-{hashlib.sha256(raw).hexdigest()[:12]}"


def fuentes_moneda(symbol: str) -> dict:
    """Fuentes en vivo de una moneda (API públicas, sin credenciales); una sesión por moneda."""
    feed = BinancePollingFeed(symbol)
    f = {"feed": feed, "sec": SecondsFeed(feed.session, symbol=symbol)}
    if symbol in COMPUESTO:
        f["venues"] = UsdtCloses(feed.session, symbol=symbol)
    return f


class Opinador:
    """Las opiniones de los modelos congelados en el segundo 50 de una vela, calculadas una sola vez por vela aunque
    las pidan varias monedas a la vez (los contratos de ETH y BTC de OKX comparten las mismas opiniones)."""

    def __init__(self, claves, fuentes: dict | None = None, bundles: dict | None = None, log=print):
        self.claves = tuple(claves)
        todo = {**gb.bases(), **gb.bases_extra()}
        self.bundles = bundles or {k: load_bundle(*todo[k]) for k in self.claves}
        if any(self.bundles[k]["k"] != K for k in self.claves):
            raise ValueError("todas las opiniones del gran bot deciden en el segundo 50")
        self.monedas = [s for s in ORDEN if s in {MONEDA_DE[k] for k in self.claves}]
        self.fuentes = dict(fuentes or {})
        for s in self.monedas:
            self.fuentes.setdefault(s, fuentes_moneda(s))
        self.log = log
        self.pool = ThreadPoolExecutor(max_workers=len(self.monedas))
        self._lock = threading.Lock()
        self._lock_prep = threading.Lock()
        self._memo: tuple = (None, None)
        self._prep: tuple = (None, None)

    def precargar(self, now: datetime) -> None:
        """Las ~2 000 velas de 1 min de cada moneda, al arrancar (no en el segundo 50)."""
        for s in self.monedas:
            try:
                self.fuentes[s]["feed"].get(now)
            except requests.RequestException as exc:
                self.log(f"{s}: sin velas al arrancar ({type(exc).__name__}); se reintenta en cada vela")

    def _previas(self, symbol: str, now: datetime, minute_open: pd.Timestamp) -> dict:
        """Lo que solo depende de velas de 1 min cerradas (Binance y, en BTC, ETH y SOL, Bybit y OKX)."""
        f = self.fuentes[symbol]
        try:
            bars, _ = f["feed"].get(now)
            if symbol in COMPUESTO:
                venues = f["venues"].recent(minute_open - pd.Timedelta(minutes=1))
                prev, cf, motivo, comp = previas_blitz(bars, venues, minute_open)
            else:
                (prev, motivo), cf, comp = previas_binance(bars, minute_open), None, None
        except (requests.RequestException, ValueError, KeyError, IndexError) as exc:
            return {"prev": None, "motivo": f"error de datos ({type(exc).__name__})"}
        return {"prev": prev, "cf": cf, "motivo": motivo, "comp": comp}

    def preparar(self, now: datetime, minute_open: pd.Timestamp) -> None:
        """Antes del segundo 50 (el bucle lo llama en el segundo 35): velas de 1 min y cierres de las otras bolsas de
        todas las monedas, para que en el segundo 50 solo falten las velas de 1 s del minuto en curso."""
        with self._lock_prep:
            res = dict(zip(self.monedas, self.pool.map(lambda s: self._previas(s, now, minute_open), self.monedas)))
            self._prep = (minute_open, res)

    def _x(self, symbol: str, now: datetime, minute_open: pd.Timestamp, pre: dict | None):
        p = (pre or {}).get(symbol)
        if p is None or p["prev"] is None:  # sin preparación (o falló): todo ahora
            p = self._previas(symbol, now, minute_open)
        if p["prev"] is None:
            return None, p["motivo"], None
        try:
            sec = self.fuentes[symbol]["sec"].get(minute_open, now)
        except (requests.RequestException, ValueError, KeyError, IndexError) as exc:
            return None, f"error de datos ({type(exc).__name__})", None
        X, motivo = con_segundos(p["prev"], sec, minute_open, K, extra=p["cf"])
        if X is None:
            return None, motivo, None
        return X.loc[:, ~X.columns.duplicated()], None, p["comp"]

    def opinar(self, now: datetime, minute_open: pd.Timestamp) -> dict:
        with self._lock:
            if self._memo[0] == minute_open:
                return self._memo[1]
            t0 = time.monotonic()
            with self._lock_prep:  # si la preparación sigue en curso, la espera
                pre = self._prep[1] if self._prep[0] == minute_open else None
            xs = dict(zip(self.monedas, self.pool.map(lambda s: self._x(s, now, minute_open, pre), self.monedas)))
            op, faltan = {}, []
            for k in self.claves:
                X, motivo, _ = xs[MONEDA_DE[k]]
                if X is None:
                    faltan.append(f"{CORTO.get(MONEDA_DE[k], MONEDA_DE[k][:-4])}: {motivo}")
                    continue
                b = self.bundles[k]
                Xb = X[b["features"]]
                if Xb.isna().any(axis=1).iloc[0]:
                    faltan.append(f"{k}: variables incompletas")
                    continue
                op[k] = float(b["calibrator"].transform(b["model"].predict_proba(Xb.to_numpy())[:, 1])[0])
            comp = {s: xs[s][2] for s in self.monedas if xs[s][2] is not None}
            res = {"opiniones": op, "faltan": sorted(set(faltan)), "compuesto": comp, "preparado": pre is not None,
                   "calculo_s": round(time.monotonic() - t0, 2)}  # datos que faltaban + modelos
            self._memo = (minute_open, res)
            return res


# ----------------------------------------------------------------------------------------------- reglas del registro
def _sin_datos(r: dict) -> dict:
    return {"estado": "sin datos", "motivo": "; ".join(r["faltan"]) or "faltan opiniones", "gran": True}


def opiniones_okx(op: dict, moneda: str, dur: int) -> dict:
    """Las opiniones con los nombres del metamodelo de una moneda (igual que `gran_bot.filas_dia` y `filas_15`)."""
    otra = [m for m in gb.MONEDAS if m != moneda][0]
    comunes = {k: op[k] for k in ("p20", "p42", "p51", "p53")}
    if dur == 5:
        return {"propia": op[f"okx5_{moneda}"], "otra": op[f"okx5_{otra}"], **comunes}
    return {"propia15": op[f"okx15_{moneda}"], "otra15": op[f"okx15_{otra}"], "propia5": op[f"okx5_{moneda}"],
            "otra5": op[f"okx5_{otra}"], **comunes}


def decidir_okx(r: dict, coef: dict, moneda: str, dur: int, umbral: float | None = None) -> dict:
    """Regla del registro: avisa si max(p, 1 − p) − costo ≥ margen (0,5312 y 0,02, Estudio 63)."""
    claves = gb.OPINIONES if dur == 5 else gb.OPINIONES_15
    try:
        opin = opiniones_okx(r["opiniones"], moneda, dur)
    except KeyError:
        return _sin_datos(r)
    p_gran = gb._combinar_con(coef, opin, claves)
    lado = 1 if p_gran >= 0.5 else -1
    p_dir = p_gran if lado == 1 else 1 - p_gran
    base = opin["propia"] if dur == 5 else opin["propia15"]
    fires = p_dir - study63.COSTO >= study63.MARGEN and (umbral is None or p_dir >= umbral)
    return {"estado": "señal" if fires else "sin señal", "lado": lado, "p": p_dir,
            "ev": (p_dir - study63.COSTO) / study63.COSTO, "p_gran": p_gran, "p_base": base,
            "senal_base": bool(max(base, 1 - base) - study63.COSTO >= study63.MARGEN),
            "opiniones": {k: round(float(v), 5) for k, v in opin.items()}, "gran": True}


def decidir_blitz(r: dict, coef: dict, q: float, pago: float, margen: float, umbral: float | None = None) -> dict:
    """Regla del registro (`gran_bot.filas_blitz`): avisa si la ganancia esperada con el pago y la tasa de empates de
    p42 es ≥ margen."""
    op = r["opiniones"]
    try:
        opin = {"propia": op["p42"], **{k: op[k] for k in gb.OPINIONES_BLITZ[1:]}}
    except KeyError:
        return _sin_datos(r)
    p_gran = gb._combinar_con(coef, opin, gb.OPINIONES_BLITZ)
    lado = 1 if p_gran >= 0.5 else -1
    p_dir = p_gran if lado == 1 else 1 - p_gran
    contrato = BinaryContract(pago, "refund")
    ev = float(contrato.ev(np.array([p_dir]), np.array([q]))[0])
    base = float(op["p42"])
    ev_base = float(contrato.ev(np.array([max(base, 1 - base)]), np.array([q]))[0])
    fires = ev >= margen and (umbral is None or p_dir >= umbral)
    return {"estado": "señal" if fires else "sin señal", "lado": lado, "p": p_dir, "ev": ev, "p_gran": p_gran,
            "p_base": base, "senal_base": bool(ev_base >= margen),
            "opiniones": {k: round(float(v), 5) for k, v in opin.items()}, "gran": True,
            "compuesto": r["compuesto"].get("BTCUSDT")}


# ----------------------------------------------------------------------------------------------- bucles
PREP_AT_S = 35.0  # segundo (hora de Binance) en que se preparan las velas cerradas de la decisión del segundo 50


def preparador(loop, turno=None, segundo: float = PREP_AT_S) -> threading.Thread:
    """Hilo que en el segundo 35 de cada vela de decisión prepara lo que no depende del minuto en curso. Si falla o
    llega tarde, la decisión del segundo 50 lo baja todo (más lenta, pero igual)."""
    def run():
        while True:
            now = pd.Timestamp(loop.feed.server_now())
            target = now.floor("min") + pd.Timedelta(seconds=segundo)
            if now >= target:
                target += pd.Timedelta(minutes=1)
            time.sleep(max(0.0, (target - now).total_seconds()))
            minute_open = target.floor("min")
            if turno is not None and not turno(minute_open):
                continue
            try:
                loop.opinador.preparar(loop.feed.server_now(), minute_open)
            except Exception as exc:  # noqa: BLE001 - el segundo 50 lo reintenta todo
                loop.log(f"preparación: {type(exc).__name__}: {exc}"[:200])

    th = threading.Thread(target=run, daemon=True, name="preparador")
    th.start()
    return th


class GranBlitzLoop(BlitzLoop):
    """Blitz de BTC de IQ Option con el gran bot (8 opiniones). Avisa solo con IQ Option abierto."""

    def __init__(self, runtime: Path, sound: bool = True, log=print, pago: float | None = None,
                 umbral: float | None = None, record: bool = True, telegram=None, horario: dict | None = None,
                 opinador: Opinador | None = None, feed=None, secfeed=None, venues=None):
        self.cfg, self.gran_id = cargar("blitz")
        claves = PRODUCTOS["blitz"]["claves"]
        bundles = opinador.bundles if opinador else {k: load_bundle(*{**gb.bases(), **gb.bases_extra()}[k])
                                                      for k in claves}
        super().__init__(bundles["p42"], runtime, feed=feed, secfeed=secfeed, venues=venues, sound=sound, log=log,
                         pago=pago, umbral=umbral, record=record, telegram=telegram, horario=horario)
        self.opinador = opinador or Opinador(claves, bundles=bundles, log=log, fuentes={
            "BTCUSDT": {"feed": self.feed, "sec": self.sec, "venues": self.venues}})
        self.q = float(bundles["p42"]["q"])
        self.extra_state.update({"gran": True, "producto": "blitz", "model_id": self.gran_id,
                                 "opiniones": list(claves), "estudios": PRODUCTOS["blitz"]["estudios"]})

    def _decide(self, a: dict, now: datetime, minute_open: pd.Timestamp) -> dict:
        r = self.opinador.opinar(now, minute_open)
        d = decidir_blitz(r, self.cfg["coeficientes"], self.q, self.pago if self.pago is not None else self.cfg["pago"],
                          self.cfg["margen"], self.umbral)
        d.update({"activo": "BTC", "symbol": "BTCUSDT", "model_id": self.gran_id, "calculo_s": r.get("calculo_s"),
                  "preparado": r.get("preparado")})
        return d

    def run(self, iterations: int = 0) -> None:
        self.opinador.precargar(self.feed.server_now())
        preparador(self)
        super().run(iterations)


class GranOkxLoop(OkxLoop):
    """Contratos de OKX de 5 o 15 min con el gran bot (6 u 8 opiniones), ETH y BTC. Mira el libro antes de avisar,
    igual que el modo OKX de siempre."""

    def __init__(self, runtime: Path, dur: int = 5, monedas=("ETHUSDT", "BTCUSDT"), sound: bool = True, log=print,
                 umbral: float | None = None, telegram=None, eventos: OkxEventos | None = None,
                 precio_max: float = PRECIO_MAX, opinador: Opinador | None = None, fuentes: dict | None = None):
        producto = "okx5" if dur == 5 else "okx15"
        self.cfg, self.gran_id = cargar(producto)
        claves = PRODUCTOS[producto]["claves"]
        todo = {**gb.bases(), **gb.bases_extra()}
        bundles = opinador.bundles if opinador else {k: load_bundle(*todo[k]) for k in claves}
        base = {s: bundles.get(f"okx{dur}_{s}") or load_bundle(*modelos(dur)[s]) for s in monedas}
        fuentes = fuentes or {}
        extra = [{"symbol": s, "bundle": base[s], **fuentes.get(s, {})} for s in monedas[1:]]
        f0 = fuentes.get(monedas[0], {})
        super().__init__(base[monedas[0]], runtime, feed=f0.get("feed"), secfeed=f0.get("sec"),
                         venues=f0.get("venues"), sound=sound, log=log, umbral=umbral, telegram=telegram, extra=extra,
                         eventos=eventos, precio_max=precio_max)
        self.dur = dur
        self.opinador = opinador or Opinador(claves, bundles=bundles, log=log, fuentes={
            a["symbol"]: {"feed": a["feed"], "sec": a["sec"], "venues": a["venues"]} for a in self.assets})
        self.extra_state.update({"gran": True, "producto": producto, "duracion_min": dur, "model_id": self.gran_id,
                                 "opiniones": list(claves), "estudios": PRODUCTOS[producto]["estudios"]})

    def _decide(self, a: dict, now: datetime, minute_open: pd.Timestamp) -> dict:
        r = self.opinador.opinar(now, minute_open)
        d = decidir_okx(r, self.cfg["coeficientes"][a["symbol"]], a["symbol"], self.dur, self.umbral)
        d.update({"activo": CORTO.get(a["symbol"], a["symbol"]), "symbol": a["symbol"], "model_id": self.gran_id,
                  "calculo_s": r.get("calculo_s"), "preparado": r.get("preparado")})
        return self._libro(a, d, minute_open)

    def run(self, iterations: int = 0) -> None:
        self.opinador.precargar(self.feed.server_now())
        preparador(self, turno=lambda m: (m.minute + 1) % self.dur == 0)
        super().run(iterations)
