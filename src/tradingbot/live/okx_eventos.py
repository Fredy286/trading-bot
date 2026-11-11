"""Modo de práctica SIN dinero para los «event contracts» de OKX «Up or Down 5min» (Estudios 54 y 55).

Cada ventana de 5 min empieza en un minuto múltiplo de 5 (hora UTC). En el segundo 50 del minuto anterior el modelo
congelado decide con la receta del blitz: vela anterior de Binance, bloque parcial hasta el segundo 49 y compuesto de 3
bolsas. Si la ganancia esperada con el precio de compra es suficiente, avisa con sonido y Telegram: qué comprar
(«Al alza» o «A la baja», los nombres de la web de OKX en español; en la API, «Up» y «Down»), en qué pestaña (la web
rotula cada ventana con su hora de CIERRE) y a qué precio máximo. **Hay que comprar antes del segundo 57:** 1–2 s antes
de que empiece la ventana el creador de mercado retira sus precios, y dentro de la ventana el diferencial se abre
(comprobado en la web y con el libro de la API el 2026-11-07/08, docs/03, 2.3).

- Antes de avisar mira el libro de órdenes de la ventana. Si comprar ese lado cuesta más de `PRECIO_MAX`, no avisa.
- La referencia de cada aviso es el **resultado oficial de OKX** (API pública: `floorStrike`, `settleValue`,
  `outcome`).

No envía órdenes: el usuario decide y anota. Nunca dinero real sin su autorización expresa.
"""

from __future__ import annotations

import hashlib
import json
import pickle
import uuid
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import requests

from ..execution.paper import read_rows
from ..research import study54 as s54
from ..research.calibration import Calibrator
from ..research.experiment import git_sha
from ..research.features import FEATURES, compute_features
from ..research.models import fit_predict_proba
from ..research.study16 import partial_features
from ..research.study20 import K
from ..research.study41 import composite
from ..research.study42 import comp_features
from ..timeutil import utcnow
from .anticipada import CALIB_FRAC, LAT, TRAIN_END, TRAIN_START
from .blitz import CORTO, BlitzLoop

DUR = 5
SERIES = {"ETHUSDT": "ETH-UPDOWN-5MIN", "BTCUSDT": "BTC-UPDOWN-5MIN"}
SERIES15 = {"ETHUSDT": "ETH-UPDOWN-15MIN", "BTCUSDT": "BTC-UPDOWN-15MIN"}  # Estudio 60
MODELOS = {"ETHUSDT": (Path("config/modelos/ETHUSDT_okx5.pkl"), Path("config/senal_okx5_eth.json")),
           "BTCUSDT": (Path("config/modelos/BTCUSDT_okx5.pkl"), Path("config/senal_okx5_btc.json"))}
MODELOS15 = {"ETHUSDT": (Path("config/modelos/ETHUSDT_okx15.pkl"), Path("config/senal_okx15_eth.json")),
             "BTCUSDT": (Path("config/modelos/BTCUSDT_okx15.pkl"), Path("config/senal_okx15_btc.json"))}
REGISTRO = {5: "Estudio 55 (pre-registro 1067c6f): modelo congelado de OKX 5 min para la confirmación y la práctica",
            15: "Estudio 60 (pre-registro 4760414): modelo congelado de OKX 15 min para la confirmación"}


def serie(symbol: str, dur: int = 5) -> str:
    return (SERIES if dur == 5 else SERIES15)[symbol]


def modelos(dur: int = 5) -> dict:
    return MODELOS if dur == 5 else MODELOS15
PRECIO_REF = 0.52   # compra antes de la ventana (Estudio 54)
PRECIO_MAX = 0.53   # por encima, no se avisa
K_TOMADOR = 0.045   # comisión del tomador por acción = K × P × (1 − P) (OKX, desde el 2026-05-06)
OKX = "https://www.okx.com"


def costo(precio: float) -> float:
    """Lo que cuesta una acción comprada como tomador, con comisión. Gana 1 USDT si acierta."""
    return precio + K_TOMADOR * precio * (1 - precio)


def pago_equivalente(precio: float = PRECIO_REF) -> float:
    """Ganancia por unidad apostada si acierta, para usar la misma cuenta del blitz: (1 − costo) / costo."""
    c = costo(precio)
    return (1 - c) / c


def margen_equivalente(precio: float = PRECIO_REF, ev_accion: float = 0.02) -> float:
    """EV mínimo por unidad apostada que equivale a ganar `ev_accion` USDT por acción."""
    return ev_accion / costo(precio)


def inst_id(symbol: str, ventana: pd.Timestamp, dur: int = DUR) -> str:
    """Nombre del contrato en OKX: la fecha y las horas van en UTC+8 (p. ej., ETH-UPDOWN-5MIN-261108-0650-0655)."""
    hk = pd.Timestamp(ventana).tz_convert("UTC").tz_localize(None) + pd.Timedelta(hours=8)
    return f"{serie(symbol, dur)}-{hk:%y%m%d}-{hk:%H%M}-{hk + pd.Timedelta(minutes=dur):%H%M}"


# ----------------------------------------------------------------------------------------------- entrenamiento
def train_frozen_okx(symbol: str, log=print, registro: str | None = None, dur: int = DUR) -> dict:
    """Entrena UNA vez el modelo del Estudio 54 (5 o 15 min) con los 12 meses hasta el 2026-10-25."""
    registro = registro or REGISTRO[dur]
    out, reg = modelos(dur)[symbol]
    if out.exists():
        raise FileExistsError(f"{out} ya existe: el modelo se entrena una sola vez (pre-registro).")
    bars_all, tab_all, cl = s54.inputs(symbol)
    bars = bars_all[(bars_all.index >= TRAIN_START - pd.Timedelta(days=3)) & (bars_all.index < TRAIN_END)]
    idx = bars.index
    tab = tab_all.reindex(idx)
    prev = compute_features(bars).shift(1)
    vol_prev = np.exp(prev["lvol60"])
    X = pd.concat([prev[FEATURES], partial_features(tab, bars["o"], vol_prev, K),
                   comp_features(composite(cl), cl["binance"], vol_prev, idx)], axis=1)
    ix = s54.index_closes(s54.SIMBOLOS[symbol]["indice"])
    y = np.full(len(idx), np.nan)
    months = [p.strftime("%Y-%m") for p in pd.period_range(idx[0].tz_convert(None), "2026-10", freq="M")]
    ym = np.asarray(idx.strftime("%Y-%m"))
    for k, m in enumerate(months):
        rows = np.flatnonzero(ym == m)
        cur = s54.sec_close(symbol, m)
        nxt = s54.sec_close(symbol, months[k + 1]).iloc[:3600] if k + 1 < len(months) else cur.iloc[:0]
        sec = pd.concat([cur, nxt]).sort_index()
        sec = sec[~sec.index.duplicated(keep="last")]
        if len(rows) and not sec.empty:
            y[rows] = s54.settle_labels(idx[rows], dur, ix, bars["c"], sec.index, sec.to_numpy(float))
    known = (idx + pd.Timedelta(minutes=dur + 3)) <= TRAIN_END
    ok = (idx >= TRAIN_START) & known & X.notna().all(axis=1).to_numpy() & ~np.isnan(y)
    rows = np.flatnonzero(ok)
    cut = idx[rows[int(len(rows) * (1 - CALIB_FRAC))]].floor("D")
    fit = ok & (idx < cut - pd.Timedelta(minutes=dur + 3))
    cal = ok & (idx >= cut)
    model, (pc,) = fit_predict_proba("gbm", X[fit], (y[fit] == 1).astype(int), [X[cal]], seed=2024,
                                     max_rows=400_000, features=list(X.columns))
    calib = Calibrator().fit(pc, (y[cal] == 1).astype(int))
    bundle = {"model": model, "calibrator": calib, "features": list(X.columns), "k": K, "latencia": LAT,
              "duracion_min": dur, "q": 0.0, "train_start": str(TRAIN_START), "train_end": str(TRAIN_END),
              "calib_desde": str(cut), "n_ajuste": int(fit.sum()), "n_calibracion": int(cal.sum()),
              "payout": pago_equivalente(), "ev_margin": margen_equivalente(), "precio_ref": PRECIO_REF,
              "symbol": symbol, "serie": serie(symbol, dur),
              "precio": f"índice de OKX {s54.SIMBOLOS[symbol]['indice']} (resultado oficial del contrato)",
              "model_id": f"{symbol}-okx{dur}-{uuid.uuid4().hex[:6]}"}
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "wb") as fh:
        pickle.dump(bundle, fh)
    sha = hashlib.sha256(out.read_bytes()).hexdigest()
    meta = {k: v for k, v in bundle.items() if k not in ("model", "calibrator")}
    meta.update({"model_file": str(out), "model_sha256": sha, "git_sha": git_sha(), "creado": utcnow().isoformat(),
                 "registro": registro})
    reg.write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    log(f"Modelo {bundle['model_id']}: ajuste={fit.sum():,} calibración={cal.sum():,} sha256={sha[:12]}…")
    return meta


# ----------------------------------------------------------------------------------------------- datos de OKX
class OkxEventos:
    """Libro de órdenes y resultados oficiales de los event contracts (API pública, sin cuenta)."""

    def __init__(self, session=None):
        self.session = session or requests.Session()

    def _get(self, path: str, **params) -> dict:
        r = self.session.get(OKX + path, params=params, timeout=5)
        r.raise_for_status()
        return r.json()

    def libro(self, inst: str, niveles: int = 5) -> dict:
        """Libro del contrato: «a» = ventas de «Al alza», «b» = compras (comprar «A la baja» cuesta 1 − b)."""
        j = self._get("/api/v5/market/books", instId=inst, sz=niveles)
        if str(j.get("code")) != "0":
            raise ValueError(f"OKX {j.get('code')}: {j.get('msg')}")
        d = (j.get("data") or [{}])[0]
        return {k: [[float(x[0]), float(x[1])] for x in d.get(src) or []] for k, src in (("a", "asks"), ("b", "bids"))}

    def precio_compra(self, inst: str, lado: int, cantidad: float = 1.0, tope: float = PRECIO_MAX):
        """(precio medio para comprar `cantidad` contratos del lado, contratos disponibles a ≤ `tope`). Precio None si
        no alcanzan. Es la misma regla del Estudio 56 (`study56.precio_un_contrato`): el mejor precio a veces trae solo
        0,3 contratos (libro grabado del 2026-11-08)."""
        from ..research.study56 import precio_un_contrato

        return precio_un_contrato(self.libro(inst), "Up" if lado == 1 else "Down", cantidad, tope)

    def resultado(self, symbol: str, inst: str, after_ms: int | None = None) -> dict | None:
        """Resultado oficial de un contrato vencido (o None si aún no está)."""
        params = {"seriesId": SERIES[symbol], "state": "expired"}
        if after_ms:
            params["after"] = after_ms
        for x in self._get("/api/v5/public/event-contract/markets", **params).get("data") or []:
            if x.get("instId") == inst and x.get("settleValue"):
                return {"outcome": x["outcome"], "partida": float(x["floorStrike"]),
                        "liquidacion": float(x["settleValue"])}
        return None


# ----------------------------------------------------------------------------------------------- bucle
def proxima_decision(minute_open: pd.Timestamp, dur: int = DUR) -> pd.Timestamp:
    """Primer minuto (desde `minute_open`) cuyo siguiente minuto abre una ventana."""
    m = pd.Timestamp(minute_open)
    while (m.minute + 1) % dur:
        m += pd.Timedelta(minutes=1)
    return m


class OkxLoop(BlitzLoop):
    def __init__(self, bundle: dict, runtime: Path, feed=None, secfeed=None, venues=None, sound: bool = True,
                 log=print, umbral: float | None = None, telegram=None, extra: list[dict] | None = None,
                 eventos: OkxEventos | None = None, precio_max: float = PRECIO_MAX):
        super().__init__(bundle, runtime, feed=feed, secfeed=secfeed, venues=venues, sound=sound, log=log, pago=None,
                         umbral=umbral, record=False, telegram=telegram, extra=extra)
        self.dur, self.precio_max = DUR, precio_max
        self.eventos = eventos or OkxEventos(self.feed.session)
        self.extra_state.update({"modo": "okx", "duracion_min": DUR, "precio_max": precio_max,
                                 "precio": "índice de OKX (resultado oficial del contrato)"})

    def _decide(self, a: dict, now: datetime, minute_open: pd.Timestamp) -> dict:
        d = super()._decide(a, now, minute_open)
        if d["estado"] != "señal":
            return d
        ventana = minute_open + pd.Timedelta(minutes=1)
        inst = inst_id(a["symbol"], ventana)
        try:
            precio, disponible = self.eventos.precio_compra(inst, d["lado"], tope=self.precio_max)
        except (requests.RequestException, ValueError, KeyError, IndexError):
            precio, disponible = None, None
        if disponible is not None:
            disponible = round(disponible, 1)
        d.update({"instrumento": inst, "ventana": ventana.isoformat(), "precio_compra": precio,
                  "disponible": disponible})
        if precio is None:  # ni 1 contrato completo a ≤ precio_max (la regla del Estudio 56)
            d.update({"estado": "sin señal",
                      "motivo": "sin precio en OKX" if disponible is None else
                      f"comprar 1 contrato cuesta más de {self.precio_max:g} (a ese precio hay {disponible:g})"})
        else:  # ganancia esperada por acción con el precio real del libro y la comisión
            d["ev_accion"] = round(d["p"] - costo(precio), 4)
        return d

    def step(self, now: datetime) -> dict:
        minute_open = pd.Timestamp(now).floor("min")
        if (minute_open.minute + 1) % self.dur:
            nxt = proxima_decision(minute_open, self.dur)
            d = {"estado": "fuera de turno", "proximo": (nxt + pd.Timedelta(seconds=self.b["k"])).isoformat()}
            if self.last.get("estado") != "señal" or pd.Timestamp(now) > pd.Timestamp(self.last["cierre"]) + pd.Timedelta(seconds=60):
                self.last = d
            return d
        return super().step(now)

    def fill_references(self, now: datetime) -> int:
        """Resultado oficial de OKX de cada aviso, en cuanto el contrato vence."""
        done = 0
        for a in read_rows(self.dir / "senales.jsonl")[0]:
            aid = a.get("alert_id")
            if a.get("evento") != "aviso" or aid in self.referenced or not a.get("instrumento"):
                continue
            vence = pd.Timestamp(a["vence"])
            if pd.Timestamp(now) < vence + pd.Timedelta(seconds=20):
                continue
            try:
                r = self.eventos.resultado(a["symbol"], a["instrumento"])
            except (requests.RequestException, ValueError, KeyError):
                r = None
            if r is None:
                continue
            sube = r["outcome"] == "1"
            res = 1 if (sube and a["lado"] == 1) or (not sube and a["lado"] == -1) else -1
            self._write({"evento": "referencia", "alert_id": aid, "entrada_ref": r["partida"],
                         "salida_ref": r["liquidacion"], "resultado_ref": res, "fuente_ref": "resultado oficial de OKX"})
            self.referenced.add(aid)
            done += 1
        return done
