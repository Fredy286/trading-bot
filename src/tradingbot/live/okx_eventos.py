"""Modo de práctica SIN dinero para los «event contracts» de OKX «Up or Down 5min» (Estudios 54 y 55).

Cada ventana de 5 min empieza en un minuto múltiplo de 5 (hora UTC). En el segundo 50 del minuto anterior el modelo
congelado decide con la receta del blitz: vela anterior de Binance, bloque parcial hasta el segundo 49 y compuesto de 3
bolsas. Si la ganancia esperada con el precio de compra es suficiente, avisa con sonido y Telegram: qué comprar
(«Up» o «Down»), de qué ventana y a qué precio máximo. **Hay que comprar antes de que empiece la ventana:** después, el
diferencial del libro de órdenes se abre.

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
MODELOS = {"ETHUSDT": (Path("config/modelos/ETHUSDT_okx5.pkl"), Path("config/senal_okx5_eth.json")),
           "BTCUSDT": (Path("config/modelos/BTCUSDT_okx5.pkl"), Path("config/senal_okx5_btc.json"))}
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
    return f"{SERIES[symbol]}-{hk:%y%m%d}-{hk:%H%M}-{hk + pd.Timedelta(minutes=dur):%H%M}"


# ----------------------------------------------------------------------------------------------- entrenamiento
def train_frozen_okx(symbol: str, log=print, registro: str = "Estudio 55") -> dict:
    """Entrena UNA vez el modelo del Estudio 54 (5 min) con los 12 meses hasta el 2026-10-25."""
    out, reg = MODELOS[symbol]
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
            y[rows] = s54.settle_labels(idx[rows], DUR, ix, bars["c"], sec.index, sec.to_numpy(float))
    known = (idx + pd.Timedelta(minutes=DUR + 3)) <= TRAIN_END
    ok = (idx >= TRAIN_START) & known & X.notna().all(axis=1).to_numpy() & ~np.isnan(y)
    rows = np.flatnonzero(ok)
    cut = idx[rows[int(len(rows) * (1 - CALIB_FRAC))]].floor("D")
    fit = ok & (idx < cut - pd.Timedelta(minutes=DUR + 3))
    cal = ok & (idx >= cut)
    model, (pc,) = fit_predict_proba("gbm", X[fit], (y[fit] == 1).astype(int), [X[cal]], seed=2024,
                                     max_rows=400_000, features=list(X.columns))
    calib = Calibrator().fit(pc, (y[cal] == 1).astype(int))
    bundle = {"model": model, "calibrator": calib, "features": list(X.columns), "k": K, "latencia": LAT,
              "duracion_min": DUR, "q": 0.0, "train_start": str(TRAIN_START), "train_end": str(TRAIN_END),
              "calib_desde": str(cut), "n_ajuste": int(fit.sum()), "n_calibracion": int(cal.sum()),
              "payout": pago_equivalente(), "ev_margin": margen_equivalente(), "precio_ref": PRECIO_REF,
              "symbol": symbol, "serie": SERIES[symbol],
              "precio": f"índice de OKX {s54.SIMBOLOS[symbol]['indice']} (resultado oficial del contrato)",
              "model_id": f"{symbol}-okx5-{uuid.uuid4().hex[:6]}"}
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

    def precio_compra(self, inst: str, lado: int) -> float | None:
        """Mejor precio para comprar «Up» (lado 1: el ask) o «Down» (lado −1: 1 − el bid de «Up»)."""
        d = self._get("/api/v5/market/ticker", instId=inst).get("data") or []
        if not d:
            return None
        ask, bid = d[0].get("askPx"), d[0].get("bidPx")
        if lado == 1:
            return float(ask) if ask not in (None, "") else None
        return round(1 - float(bid), 6) if bid not in (None, "") else None

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
            precio = self.eventos.precio_compra(inst, d["lado"])
        except (requests.RequestException, ValueError, KeyError):
            precio = None
        d.update({"instrumento": inst, "ventana": ventana.isoformat(), "precio_compra": precio})
        if precio is None or precio > self.precio_max:
            d.update({"estado": "sin señal",
                      "motivo": f"comprar cuesta {precio} (> {self.precio_max})" if precio else "sin precio en OKX"})
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
