"""Modo de práctica del blitz de BTC de IQ Option (3 min desde la compra, pago 86 %) para cuenta DEMO.

Estudio 42 (pre-registro 78891ce): IQ Option liquida BTC con un promedio de bolsas en USDT, que aquí se reconstruye
como el promedio de los cierres de 1 min de Binance, Bybit y OKX («el compuesto»). En el segundo 50 de cada vela, el
modelo congelado del Estudio 44 decide con las variables de Binance (vela anterior y velas de 1 s hasta el segundo 49)
y tres variables del compuesto. Si la ganancia esperada con el pago del 86 % supera el margen, avisa con sonido; el
blitz empieza con el clic (idealmente al cierre de la vela) y vence 3 min después.

Mismos archivos y reglas que `anticipada` (un archivo, un escritor). La referencia de cada aviso es el resultado con
el compuesto: cierre de la vela del aviso → cierre 3 min después. No envía órdenes a ningún intermediario.
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

from ..research.calibration import Calibrator
from ..research.contracts import BinaryContract
from ..research.experiment import git_sha
from ..research.features import FEATURES, compute_features
from ..research.models import fit_predict_proba
from ..research.study3 import load, spot_bars
from ..research.study16 import minute_table, partial_features
from ..research.study20 import build_table
from ..execution.paper import read_rows
from ..research.study41 import composite
from ..research.study42 import comp_features, label3
from ..research.study42 import closes as hist_closes
from ..timeutil import utcnow
from .anticipada import CALIB_FRAC, K, LAT, TRAIN_END, TRAIN_START, SignalLoop, download_daily

PAYOUT, DUR = 0.86, 3
MODEL_PATH = Path("config/modelos/BTCUSDT_blitz3_compuesto.pkl")
REG_PATH = Path("config/senal_blitz.json")
HIST_MIN = 70  # cierres que necesitan las variables del compuesto (media de 60 min + 4 + margen)
VENUES = ("bybit", "okx")  # Binance llega por el feed de 1 min de siempre


# ----------------------------------------------------------------------------------------------- entrenamiento
def train_frozen_blitz(root3: Path = Path("data/raw/estudio3"), daily_cache: Path = Path("data/processed/senal/diario"),
                       out: Path = MODEL_PATH, reg: Path = REG_PATH, log=print) -> dict:
    """Entrena UNA vez el modelo del Estudio 42 con los 12 meses hasta el 2026-10-25 (Estudio 44)."""
    if Path(out).exists():
        raise FileExistsError(f"{out} ya existe: el modelo se entrena una sola vez (pre-registro).")
    m_daily = download_daily("1m", "2026-10-01", "2026-10-26", daily_cache)
    spot = pd.concat([load(root3, "BTCUSDT", "spot"), m_daily])
    spot = spot[~spot.index.duplicated(keep="last")].sort_index()
    bars = spot_bars(spot)
    bars = bars[(bars.index >= TRAIN_START - pd.Timedelta(days=3)) & (bars.index < TRAIN_END)]
    idx = bars.index
    tab = build_table().reindex(idx)
    prev = compute_features(bars).shift(1)
    vol_prev = np.exp(prev["lvol60"])
    cl = hist_closes("2025-10", "2026-10")
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
              "payout": PAYOUT, "ev_margin": 0.02, "precio": "promedio de Binance, Bybit y OKX (BTC/USDT, 1 min)",
              "model_id": f"BTCUSDT-blitz3-compuesto-{uuid.uuid4().hex[:6]}"}
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    with open(out, "wb") as fh:
        pickle.dump(bundle, fh)
    sha = hashlib.sha256(Path(out).read_bytes()).hexdigest()
    meta = {k: v for k, v in bundle.items() if k not in ("model", "calibrator")}
    meta.update({"model_file": str(out), "model_sha256": sha, "git_sha": git_sha(), "creado": utcnow().isoformat(),
                 "registro": "Estudio 44 (pre-registro c6ef641): modelo congelado del blitz para la confirmación y la demo"})
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


# ----------------------------------------------------------------------------------------------- datos en vivo
def _ms(t: pd.Timestamp) -> int:
    return int(t.timestamp() * 1000)


# Las mismas peticiones del Estudio 41, pero con un solo intento y 5 s de espera: en vivo no se puede bloquear el bucle
# (el Estudio 41 reintenta hasta seis veces). Ventanas de ≤ 100 min (tope de OKX por petición).
REQUESTS = {
    "binance": ("https://api.binance.com/api/v3/klines",
                lambda a, b: {"symbol": "BTCUSDT", "interval": "1m", "startTime": _ms(a), "endTime": _ms(b), "limit": 100},
                lambda j: [(int(x[0]), float(x[4])) for x in j]),
    "bybit": ("https://api.bybit.com/v5/market/kline",
              lambda a, b: {"category": "spot", "symbol": "BTCUSDT", "interval": "1", "start": _ms(a), "end": _ms(b),
                            "limit": 100},
              lambda j: [(int(x[0]), float(x[4])) for x in j["result"]["list"]]),
    "okx": ("https://www.okx.com/api/v5/market/history-candles",
            lambda a, b: {"instId": "BTC-USDT", "bar": "1m", "after": _ms(b) + 1, "before": _ms(a) - 1, "limit": 100},
            lambda j: [(int(x[0]), float(x[4])) for x in j["data"] if len(x) < 9 or x[8] == "1"]),
}


class UsdtCloses:
    """Cierres de 1 min ya cerrados de BTC/USDT en Binance, Bybit y OKX (API públicas, sin credenciales)."""

    def __init__(self, session=None):
        self.session = session or requests.Session()

    def get(self, venue: str, a: pd.Timestamp, b: pd.Timestamp) -> pd.Series:
        url, params, parse = REQUESTS[venue]
        r = self.session.get(url, params=params(a, b), timeout=5)
        r.raise_for_status()
        s = pd.Series({pd.Timestamp(t, unit="ms", tz="UTC"): c for t, c in parse(r.json())}, dtype=float).sort_index()
        return s[(s.index >= a) & (s.index <= b)]

    def recent(self, t1: pd.Timestamp, n: int = HIST_MIN + 5) -> dict[str, pd.Series]:
        a = t1 - pd.Timedelta(minutes=n - 1)
        return {v: self.get(v, a, t1) for v in VENUES}


# ----------------------------------------------------------------------------------------------- bucle
class BlitzLoop(SignalLoop):
    def __init__(self, bundle: dict, runtime: Path, feed=None, secfeed=None, venues=None, sound: bool = True,
                 log=print, pago: float | None = None, umbral: float | None = None):
        super().__init__(bundle, runtime, feed=feed, secfeed=secfeed, sound=sound, log=log, pago=pago, umbral=umbral)
        self.venues = venues or UsdtCloses(self.feed.session)
        self.extra_state = {"modo": "blitz", "duracion_min": DUR, "precio": bundle.get("precio")}

    def step(self, now: datetime) -> dict:
        minute_open = pd.Timestamp(now).floor("min")
        bars, _ = self.feed.get(now)
        sec = self.sec.get(minute_open, now)
        venues = self.venues.recent(minute_open - pd.Timedelta(minutes=1))
        d = decide_blitz(self.b, bars, sec, venues, minute_open, self.pago, self.umbral)
        self.n_minutes += 1
        d.update({"vela": minute_open.isoformat(), "decidido": pd.Timestamp(now).isoformat(),
                  "cierre": (minute_open + pd.Timedelta(minutes=1)).isoformat(),
                  "vence": (minute_open + pd.Timedelta(minutes=1 + DUR)).isoformat()})
        if d["estado"] == "señal":
            self.n_signals += 1
            d["alert_id"] = uuid.uuid4().hex[:12]
            d["emitido"] = pd.Timestamp(self.feed.server_now()).isoformat()
            self._write({"evento": "aviso", "model_id": self.b["model_id"], **d})
            self._beep()
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
            closes = {v: self.venues.get(v, t, end) for v in VENUES}
            closes["binance"] = self.venues.get("binance", t, end)
            comp = composite(closes)
            o, e = comp.get(t), comp.get(end)
            res = None if o is None or e is None else int(np.sign(round((e - o) / 0.005)) * a["lado"])
            self._write({"evento": "referencia", "alert_id": aid, "entrada_ref": o, "salida_ref": e,
                         "resultado_ref": res, "fuente_ref": "promedio de Binance, Bybit y OKX"})
            self.referenced.add(aid)
            done += 1
        return done
