"""Modo de señales anticipadas para cuenta DEMO (Estudio 16, hipótesis H16b; pre-registro dc5ff77).

En el segundo 50 de cada vela de 1 minuto de BTC/USDT (hora de Binance), el modelo decide con `FEATURES` de la vela
anterior y el bloque parcial de la vela en curso (velas de 1 s hasta el segundo 49). Si la ganancia esperada supera
el margen, avisa con sonido: el usuario hace clic en su plataforma demo, idealmente antes del cierre de la vela.

Archivos en la carpeta de trabajo (un archivo, un escritor):
- `senales.jsonl` y `state.json`: los escribe SOLO este bucle (avisos y precios de referencia de Binance).
- `clics.jsonl` y `registros.jsonl`: los escribe SOLO el panel (hora del clic y datos de la plataforma).

No envía órdenes a ningún intermediario: el usuario opera a mano y solo en demo.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import pickle
import shutil
import subprocess
import time
import uuid
import zipfile
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import requests

from .. import jsonutil
from ..data.http import NotFound, get_bytes, make_session
from ..execution.paper import read_rows
from ..research.calibration import Calibrator
from ..research.contracts import BinaryContract
from ..research.experiment import git_sha
from ..research.features import FEATURES, compute_features
from ..research.models import fit_predict_proba
from ..research.study3 import _read_klines, load, spot_bars
from ..research.study16 import _read_sec, label, minute_table, partial_features
from ..timeutil import BOGOTA, utcnow
from .feeds import BinancePollingFeed

K, LAT = 50, 10  # H16b: aviso en el segundo 50, clic previsto 10 s después (al cierre)
TRAIN_START = pd.Timestamp("2025-10-26", tz="UTC")  # 12 meses hasta el 2026-10-25 (pre-registro)
TRAIN_END = pd.Timestamp("2026-10-26", tz="UTC")  # excluido
CALIB_FRAC = 0.2
MODEL_PATH = Path("config/modelos/BTCUSDT_senal_anticipada_k50.pkl")
REG_PATH = Path("config/senal_anticipada.json")
DAILY_URL = "https://data.binance.vision/data/spot/daily/klines/{s}/{i}/{s}-{i}-{d}.zip"
SOUND = "/usr/share/sounds/freedesktop/stereo/complete.oga"
FIRE_AT_S = 50.25  # segundo de la vela en que se decide (hora de Binance), con margen de publicación


# ----------------------------------------------------------------------------------------------- datos y entrenamiento
def download_daily(interval: str, start: str, end: str, cache: Path, symbol: str = "BTCUSDT") -> pd.DataFrame:
    """Archivos diarios de Binance (1m o 1s) en [start, end), con caché en disco."""
    session, parts = make_session(), []
    for d in pd.date_range(start, end, freq="D", inclusive="left"):
        f = Path(cache) / interval / f"{d:%Y-%m-%d}.parquet"
        if not f.exists():
            try:
                raw = get_bytes(session, DAILY_URL.format(s=symbol, i=interval, d=f"{d:%Y-%m-%d}"), timeout=300)
            except NotFound as exc:
                raise FileNotFoundError(f"Binance aún no publica {interval} del {d:%Y-%m-%d}") from exc
            with zipfile.ZipFile(io.BytesIO(raw)) as zf:
                csv = zf.read(zf.namelist()[0])
            df = _read_klines(csv) if interval == "1m" else _read_sec(csv)
            f.parent.mkdir(parents=True, exist_ok=True)
            df.to_parquet(f)
        parts.append(pd.read_parquet(f))
    return pd.concat(parts).sort_index()


def _training_table(sec_monthly: Path, sec_daily: pd.DataFrame, minutes: pd.DatetimeIndex) -> pd.DataFrame:
    """`minute_table` del Estudio 16 por meses (la memoria no admite un año de segundos de una vez)."""
    files = sorted(Path(sec_monthly).glob("*.parquet"))
    sources = [pd.read_parquet(f) for f in files] + [sec_daily]
    parts = []
    for i, sec in enumerate(sources):
        if i + 1 < len(sources):
            nxt = sources[i + 1]
            sec = pd.concat([sec, nxt[nxt.index < nxt.index[0].floor("min") + pd.Timedelta(minutes=5)]])
        mins = minutes[(minutes >= sec.index[0].floor("min")) &
                       (minutes <= sec.index[-1].floor("min") - pd.Timedelta(minutes=3))]
        if len(mins):
            parts.append(minute_table(sec, mins))
    tab = pd.concat(parts)
    return tab[~tab.index.duplicated(keep="first")]


def train_frozen(root3: Path = Path("data/raw/estudio3"), sec_monthly: Path = Path("data/processed/senal/seg"),
                 daily_cache: Path = Path("data/processed/senal/diario"), out: Path = MODEL_PATH,
                 reg: Path = REG_PATH, log=print) -> dict:
    """Entrena UNA vez el modelo H16b con los 12 meses hasta el 2026-10-25 (el de la confirmación del Estudio 16)."""
    if Path(out).exists():
        raise FileExistsError(f"{out} ya existe: el modelo se entrena una sola vez (pre-registro).")
    sec_daily = download_daily("1s", "2026-10-01", "2026-10-26", daily_cache)
    m_daily = download_daily("1m", "2026-10-01", "2026-10-26", daily_cache)
    spot = pd.concat([load(root3, "BTCUSDT", "spot"), m_daily])
    spot = spot[~spot.index.duplicated(keep="last")].sort_index()
    bars = spot_bars(spot)
    bars = bars[(bars.index >= TRAIN_START - pd.Timedelta(days=3)) & (bars.index < TRAIN_END)]
    prev = compute_features(bars).shift(1)
    minutes = bars.index[bars.index >= TRAIN_START]
    tab = _training_table(sec_monthly, sec_daily, minutes).reindex(bars.index)
    X = pd.concat([prev[FEATURES], partial_features(tab, bars["o"], np.exp(prev["lvol60"]), K)], axis=1)
    y = label(tab, K, LAT)
    known = (bars.index + pd.Timedelta(minutes=3)) <= TRAIN_END  # resultado conocido antes del fin
    ok = (bars.index >= TRAIN_START) & known & X.notna().all(axis=1).to_numpy() & ~np.isnan(y)
    rows = np.flatnonzero(ok)
    cut = bars.index[rows[int(len(rows) * (1 - CALIB_FRAC))]].floor("D")
    fit = ok & (bars.index < cut - pd.Timedelta(minutes=3)) & (y != 0)  # purga entre ajuste y calibración
    cal = ok & (bars.index >= cut) & (y != 0)
    model, (pc,) = fit_predict_proba("gbm", X[fit], (y[fit] == 1).astype(int), [X[cal]], seed=2024,
                                     features=list(X.columns))
    calib = Calibrator().fit(pc, (y[cal] == 1).astype(int))
    q = float(np.mean(y[ok & (bars.index >= cut)] == 0))  # tasa de empates del tramo de calibración
    bundle = {"model": model, "calibrator": calib, "features": list(X.columns), "k": K, "latencia": LAT, "q": q,
              "train_start": str(TRAIN_START), "train_end": str(TRAIN_END), "calib_desde": str(cut),
              "n_ajuste": int(fit.sum()), "n_calibracion": int(cal.sum()), "payout": 0.85, "ev_margin": 0.02,
              "model_id": f"BTCUSDT-anticipada-k{K}-L{LAT}-{uuid.uuid4().hex[:6]}"}
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    with open(out, "wb") as fh:
        pickle.dump(bundle, fh)
    sha = hashlib.sha256(Path(out).read_bytes()).hexdigest()
    meta = {k: v for k, v in bundle.items() if k not in ("model", "calibrator")}
    meta.update({"model_file": str(out), "model_sha256": sha, "git_sha": git_sha(), "creado": utcnow().isoformat(),
                 "registro": "Estudio 16, H16b (pre-registro dc5ff77): modelo congelado para la confirmación y la demo"})
    Path(reg).write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    log(f"Modelo {bundle['model_id']}: ajuste={fit.sum():,} calibración={cal.sum():,} q={q:.4f} sha256={sha[:12]}…")
    return meta


def load_bundle(path: Path = MODEL_PATH, reg: Path = REG_PATH) -> dict:
    meta = jsonutil.load(reg)
    sha = hashlib.sha256(Path(path).read_bytes()).hexdigest()
    if sha != meta["model_sha256"]:
        raise ValueError(f"{path} no es el modelo registrado (SHA-256 {sha[:12]}… ≠ {meta['model_sha256'][:12]}…)")
    with open(path, "rb") as fh:
        return pickle.load(fh)


# ----------------------------------------------------------------------------------------------- decisión
def decide(bundle: dict, bars: pd.DataFrame, sec: pd.DataFrame, minute_open: pd.Timestamp,
           payout: float | None = None, umbral: float | None = None) -> dict:
    """Decisión en el segundo k de la vela `minute_open`. `bars`: velas de 1 min CERRADAS (hasta la anterior);
    `sec`: velas de 1 s CERRADAS de la vela en curso (columnas o, h, l, c, v, tb, n). `payout`: pago real de la
    plataforma (por defecto, el del modelo). `umbral`: probabilidad mínima de la dirección (Estudio 21)."""
    if bars.index[-1] != minute_open - pd.Timedelta(minutes=1):
        return {"estado": "sin datos", "motivo": "falta la vela de 1 min anterior"}
    sec = sec[(sec.index >= minute_open) & (sec.index < minute_open + pd.Timedelta(seconds=bundle["k"]))]
    if sec.empty:
        return {"estado": "sin datos", "motivo": "sin velas de 1 s de la vela en curso"}
    prev = compute_features(bars).iloc[[-1]]
    prev.index = pd.DatetimeIndex([minute_open])
    tab = minute_table(sec, pd.DatetimeIndex([minute_open]))
    part = partial_features(tab, pd.Series(sec["o"].iloc[0], index=[minute_open]),
                            np.exp(prev["lvol60"]), bundle["k"])
    X = pd.concat([prev[FEATURES], part], axis=1)[bundle["features"]]
    if X.isna().any(axis=1).iloc[0]:
        return {"estado": "sin datos", "motivo": "variables incompletas (faltan segundos o historia)"}
    p_up = float(bundle["calibrator"].transform(bundle["model"].predict_proba(X.to_numpy())[:, 1])[0])
    side = 1 if p_up >= 0.5 else -1
    p_dir = p_up if side == 1 else 1 - p_up
    b = bundle["payout"] if payout is None else payout
    ev = float(BinaryContract(b, "refund").ev(np.array([p_dir]), np.array([bundle["q"]]))[0])
    fires = ev >= bundle["ev_margin"] and (umbral is None or p_dir >= umbral)
    return {"estado": "señal" if fires else "sin señal", "lado": side, "p": p_dir, "ev": ev}


# ----------------------------------------------------------------------------------------------- datos en vivo
class SecondsFeed:
    """Velas de 1 s de la API pública de Binance (sin credenciales)."""

    URL = "https://api.binance.com/api/v3/klines"

    def __init__(self, session=None):
        self.session = session or requests.Session()

    def get(self, start: pd.Timestamp, now: datetime, limit: int = 120) -> pd.DataFrame:
        r = self.session.get(self.URL, params={"symbol": "BTCUSDT", "interval": "1s",
                                               "startTime": int(start.value // 10**6), "limit": limit}, timeout=5)
        r.raise_for_status()
        rows = [k for k in r.json() if k[6] < pd.Timestamp(now).value // 10**6]  # solo velas ya cerradas
        idx = pd.DatetimeIndex(pd.to_datetime([k[0] for k in rows], unit="ms", utc=True), name="time")
        cols = {"o": 1, "h": 2, "l": 3, "c": 4, "v": 5, "n": 8, "tb": 9}
        return pd.DataFrame({c: np.array([float(k[i]) for k in rows]) for c, i in cols.items()}, index=idx)


def last_before(sec: pd.DataFrame, t: pd.Timestamp, max_gap_s: int = 5) -> float | None:
    """Último precio negociado antes del instante t (vela de 1 s que abre como mucho en t − 1 s)."""
    s = sec[sec.index <= t - pd.Timedelta(seconds=1)]
    if s.empty or (t - pd.Timedelta(seconds=1) - s.index[-1]) > pd.Timedelta(seconds=max_gap_s):
        return None
    return float(s["c"].iloc[-1])


# ----------------------------------------------------------------------------------------------- bucle
def quarter_turn(minute_open: pd.Timestamp, r: int) -> bool:
    """Vencimiento fijo cada 15 min (Estudio 19): la vela del aviso deja el vencimiento, R min después de la
    entrada, justo en :00, :15, :30 o :45."""
    return (minute_open.minute + 1 + r) % 15 == 0


class SignalLoop:
    def __init__(self, bundle: dict, runtime: Path, feed=None, secfeed=None, sound: bool = True, log=print,
                 cuarto_r: int | None = None, pago: float | None = None, umbral: float | None = None):
        self.b, self.dir = bundle, Path(runtime)
        self.cuarto_r, self.pago, self.umbral = cuarto_r, pago, umbral
        self.dir.mkdir(parents=True, exist_ok=True)
        self.feed = feed or BinancePollingFeed("BTCUSDT")
        self.sec = secfeed or SecondsFeed(self.feed.session)
        self.sound, self.log = sound, log
        self.extra_state: dict = {}  # datos propios de cada modo (el blitz los usa) que se añaden a state.json
        self.last: dict = {}
        self.started = utcnow()
        self.n_minutes = self.n_signals = 0
        self.referenced: set[str] = {r["alert_id"] for r in read_rows(self.dir / "senales.jsonl")[0]
                                     if r.get("evento") == "referencia"}

    def _write(self, row: dict) -> None:
        jsonutil.append_line(self.dir / "senales.jsonl", jsonutil.dumps(row))

    def step(self, now: datetime) -> dict:
        minute_open = pd.Timestamp(now).floor("min")
        r = self.cuarto_r
        if r and not quarter_turn(minute_open, r):
            nxt = minute_open + pd.Timedelta(minutes=1)
            while not quarter_turn(nxt, r):
                nxt += pd.Timedelta(minutes=1)
            d = {"estado": "fuera de turno", "proximo": (nxt + pd.Timedelta(seconds=self.b["k"])).isoformat()}
            self.last = d
            return d
        bars, _ = self.feed.get(now)
        sec = self.sec.get(minute_open, now)
        d = decide(self.b, bars, sec, minute_open, self.pago, self.umbral)
        self.n_minutes += 1
        d.update({"vela": minute_open.isoformat(), "decidido": pd.Timestamp(now).isoformat(),
                  "cierre": (minute_open + pd.Timedelta(minutes=1)).isoformat()})
        if r:
            d["vence"] = (minute_open + pd.Timedelta(minutes=1 + r)).isoformat()
        if d["estado"] == "señal":
            self.n_signals += 1
            d["alert_id"] = uuid.uuid4().hex[:12]
            d["emitido"] = pd.Timestamp(self.feed.server_now()).isoformat()  # retraso propio: datos + modelo
            self._write({"evento": "aviso", "model_id": self.b["model_id"], **d})
            self._beep()
        self.last = d
        return d

    def _beep(self) -> None:
        if self.sound and shutil.which("paplay") and Path(SOUND).exists():
            subprocess.Popen(["paplay", SOUND], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def fill_references(self, now: datetime) -> int:
        """Para cada clic con más de 65 s, el resultado según Binance: entrada = último precio antes del clic,
        salida = último precio antes del clic + 60 s."""
        alerts = {r["alert_id"]: r for r in read_rows(self.dir / "senales.jsonl")[0] if r.get("evento") == "aviso"}
        done = 0
        for c in read_rows(self.dir / "clics.jsonl")[0]:
            aid = c.get("alert_id")
            if aid in self.referenced or aid not in alerts or not c.get("hora_binance"):
                continue
            t_click = pd.Timestamp(c["hora_binance"])
            if pd.Timestamp(now) < t_click + pd.Timedelta(seconds=65):
                continue
            sec = self.sec.get(t_click - pd.Timedelta(seconds=10), now, limit=90)
            o, e = last_before(sec, t_click), last_before(sec, t_click + pd.Timedelta(seconds=60))
            res = None if o is None or e is None else int(np.sign(round((e - o) / 0.005)) * alerts[aid]["lado"])
            self._write({"evento": "referencia", "alert_id": aid, "entrada_binance": o, "salida_binance": e,
                         "resultado_binance": res, "latencia_s": (t_click - pd.Timestamp(alerts[aid]["decidido"]))
                         .total_seconds()})
            self.referenced.add(aid)
            done += 1
        return done

    def write_state(self, now: datetime) -> None:
        state = {"actualizado": utcnow().isoformat(), "hora_binance": pd.Timestamp(now).isoformat(),
                 "desfase_reloj_s": self.feed.offset_s, "inicio": self.started.isoformat(),
                 "model_id": self.b["model_id"], "k": self.b["k"], "latencia_prevista": self.b["latencia"],
                 "cuarto_r": self.cuarto_r, "umbral": self.umbral, "pago": self.pago if self.pago is not None else self.b["payout"],
                 "minutos": self.n_minutes, "avisos": self.n_signals, "ultimo": self.last, **self.extra_state}
        tmp = self.dir / f"state.json.{os.getpid()}.tmp"
        tmp.write_text(jsonutil.dumps(state, default=str), encoding="utf-8")
        tmp.replace(self.dir / "state.json")

    def run(self, iterations: int = 0) -> None:
        for intento in range(5):  # al arrancar: hora de Binance y ~2 000 velas precargadas (no en el segundo 50)
            try:
                self.feed.clock_offset()
                self.feed.get(self.feed.server_now())
                break
            except requests.RequestException as exc:
                self.log(f"sin conexión con Binance ({type(exc).__name__}); reintento {intento + 1}/5")
                time.sleep(5)
        done, last_sync = 0, time.time()
        while iterations <= 0 or done < iterations:
            now = pd.Timestamp(self.feed.server_now())
            target = now.floor("min") + pd.Timedelta(seconds=FIRE_AT_S)
            if now >= target:
                target += pd.Timedelta(minutes=1)
            time.sleep(max(0.0, (target - now).total_seconds()))
            now = pd.Timestamp(self.feed.server_now())
            try:
                d = self.step(now.to_pydatetime())
                self.fill_references(now.to_pydatetime())
                hora = now.tz_convert(BOGOTA).strftime("%H:%M:%S")
                if d["estado"] == "señal":
                    self.log(f"{hora}  AVISO: {'SUBE ↑' if d['lado'] == 1 else 'BAJA ↓'}  p={d['p']:.3f}  EV={d['ev']:+.3f}")
                else:
                    self.log(f"{hora}  {d['estado']}" + (f" ({d['motivo']})" if d.get("motivo") else ""))
            except (requests.RequestException, ValueError, KeyError) as exc:
                self.last = {"estado": "error", "motivo": f"{type(exc).__name__}: {exc}"[:200]}
                self.log(f"error: {self.last['motivo']}")
            self.write_state(now.to_pydatetime())
            if time.time() - last_sync > 600:
                try:
                    self.feed.clock_offset()
                    last_sync = time.time()
                except requests.RequestException as exc:  # sin internet: se sigue con el último desfase
                    self.log(f"no se pudo sincronizar el reloj ({type(exc).__name__}); se reintenta")
            done += 1
            time.sleep(1.0)


# ----------------------------------------------------------------------------------------------- diario y resumen
RESULTADOS = {"gano": 1, "perdio": -1, "empate": 0}


def diario(runtime: Path, limit: int = 50) -> list[dict]:
    """Una fila por aviso con el clic, la referencia y lo que anotó el usuario de su plataforma. La referencia es el
    precio de Binance (este modo) o el compuesto (blitz); `*_ref` la da en los dos casos."""
    d = Path(runtime)
    rows, _ = read_rows(d / "senales.jsonl")
    avisos = [r for r in rows if r.get("evento") == "aviso"]
    refs = {r["alert_id"]: r for r in rows if r.get("evento") == "referencia"}
    clics: dict[str, dict] = {}
    for c in read_rows(d / "clics.jsonl")[0]:
        clics.setdefault(c.get("alert_id"), c)  # vale el primer clic
    regs: dict[str, dict] = {}
    for g in read_rows(d / "registros.jsonl")[0]:
        regs[g.get("alert_id")] = {**regs.get(g.get("alert_id"), {}), **g}  # el último dato de cada campo
    out = []
    for a in avisos[-limit:][::-1]:
        aid = a["alert_id"]
        c, r, g = clics.get(aid, {}), refs.get(aid, {}), regs.get(aid, {})
        lat = None
        if c.get("hora_binance"):
            lat = (pd.Timestamp(c["hora_binance"]) - pd.Timestamp(a["decidido"])).total_seconds()
        res_p = RESULTADOS.get(g.get("resultado"))
        ref = {k: r.get(f"{k}_ref", r.get(f"{k}_binance")) for k in ("entrada", "salida", "resultado")}
        out.append({"alert_id": aid, "decidido": a["decidido"], "cierre": a["cierre"], "vence": a.get("vence"),
                    "lado": a["lado"], "p": a["p"], "ev": a["ev"], "clic": c.get("hora_binance"), "latencia_s": lat,
                    "entrada_binance": r.get("entrada_binance"), "salida_binance": r.get("salida_binance"),
                    "resultado_binance": r.get("resultado_binance"), "entrada_ref": ref["entrada"],
                    "salida_ref": ref["salida"], "resultado_ref": ref["resultado"],
                    "entrada_plataforma": g.get("entrada"), "salida_plataforma": g.get("salida"), "pago": g.get("pago"),
                    "resultado_plataforma": res_p,
                    "coinciden": None if res_p is None or ref["resultado"] is None else res_p == ref["resultado"]})
    return out


def resumen(runtime: Path, pago_def: float = 0.85) -> dict:
    """`pago_def`: pago supuesto cuando el usuario no anotó el de su plataforma (85 % aquí; 86 % en el blitz)."""
    filas = diario(runtime, limit=10**9)
    lat = np.array([f["latencia_s"] for f in filas if f["latencia_s"] is not None], float)
    rb = [f["resultado_ref"] for f in filas if f["resultado_ref"] is not None]
    rp = [f for f in filas if f["resultado_plataforma"] is not None]
    pagos = np.array([float(f["pago"]) for f in filas if f["pago"] not in (None, "")], float)
    pnl = [((float(f["pago"]) / 100 if f["pago"] not in (None, "") else pago_def) if f["resultado_plataforma"] > 0
            else (-1.0 if f["resultado_plataforma"] < 0 else 0.0)) for f in rp]

    def hit(v):
        nt = [x for x in v if x != 0]
        return (sum(1 for x in nt if x > 0) / len(nt)) if nt else None

    co = [f["coinciden"] for f in filas if f["coinciden"] is not None]
    return {"avisos": len(filas), "clics": int(len(lat)),
            "latencia_mediana_s": float(np.median(lat)) if len(lat) else None,
            "latencia_p90_s": float(np.percentile(lat, 90)) if len(lat) else None,
            "con_referencia": len(rb), "acierto_ref": hit(rb),
            "con_referencia_binance": len(rb), "acierto_binance": hit(rb),  # nombres anteriores (modo de 1 min)
            "anotadas_plataforma": len(rp), "acierto_plataforma": hit([f["resultado_plataforma"] for f in rp]),
            "empates_plataforma": sum(1 for f in rp if f["resultado_plataforma"] == 0),
            "pago_medio": float(pagos.mean()) if len(pagos) else None,
            "ganancia_demo_por_unidad": float(sum(pnl)) if pnl else None,
            "coincidencia_ref_plataforma": (sum(co) / len(co)) if co else None,
            "coincidencia_binance_plataforma": (sum(co) / len(co)) if co else None, "n_comparables": len(co)}
