"""Señales de reversión nocturna en divisas para cuenta DEMO (Estudios 25, 27 y 28).

Cada minuto, justo después del cierre de la vela de 1 min, se piden a la API pública de Deriv (sin cuenta) las últimas
velas de cada par (precio medio). Si la vela recién cerrada queda fuera de las bandas de Bollinger (20, 2) dentro de
la ventana nocturna, se avisa con sonido: CALL si cerró por debajo, PUT si cerró por encima, vencimiento de 3 min.
Unos 3½ min después se mide el resultado con los ticks de Deriv, desde la hora del clic del usuario (o +10 s si no
hizo clic), igual que el Estudio 27.

Archivos (un archivo, un escritor): `senales.jsonl` y `state.json` los escribe SOLO este bucle; `clics.jsonl` lo
escribe SOLO el panel. No envía órdenes a ningún intermediario.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from .. import jsonutil
from ..execution.paper import read_rows
from ..timeutil import BOGOTA, utcnow

DERIV_WS = "wss://api.derivws.com/trading/v1/options/ws/public"
# Pares de los Estudios 25/27 que Deriv publica (faltan CADCHF, CADJPY, CHFJPY, NZDCAD y NZDCHF)
PAIRS = ("AUDCAD", "AUDCHF", "AUDJPY", "AUDNZD", "AUDUSD", "EURAUD", "EURCAD", "EURCHF", "EURGBP", "EURJPY", "EURNZD",
         "GBPAUD", "GBPCAD", "GBPCHF", "GBPJPY", "GBPNZD", "NZDJPY", "NZDUSD", "USDCAD")
N_BAND, K_SD = 20, 2.0
DUR_S, LAT_DEFAULT_S, LATE_S = 180, 10, 15
FIRE_AT_S = 1.5  # segundo del minuto en que se decide (la vela anterior ya cerró)
SOUND = "/usr/share/sounds/freedesktop/stereo/complete.oga"


def in_window(t: pd.Timestamp, ventana: str) -> bool:
    """`t` = apertura de la vela en la que se entra (cierre de la vela de la señal)."""
    if ventana == "nueva_york":
        return 17 <= t.tz_convert("America/New_York").hour < 20
    return t.tz_convert("UTC").hour >= 21


def auto_window(path: Path = Path("results/estudio28/resultado.json")) -> str:
    """Ventana elegida por la regla pre-registrada del Estudio 28 (por defecto, la UTC del Estudio 27)."""
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))["ventana_en_vivo"]
    except (OSError, ValueError, KeyError):
        return "utc"


def band_side(closes: np.ndarray) -> int:
    """+1 (CALL) si el último cierre queda bajo la banda inferior, −1 (PUT) si queda sobre la superior, 0 si no."""
    if len(closes) < N_BAND or np.isnan(closes[-N_BAND:]).any():
        return 0
    w = closes[-N_BAND:]
    mid, sd = w.mean(), w.std(ddof=0)
    if w[-1] > mid + K_SD * sd:
        return -1
    if w[-1] < mid - K_SD * sd:
        return 1
    return 0


def price_before(times: np.ndarray, prices: np.ndarray, t: float, max_age: float = 60.0) -> float | None:
    """Último tick ANTES del instante t (epoch, s), si tiene ≤ max_age s."""
    i = int(np.searchsorted(times, t, side="left")) - 1
    if i < 0 or t - times[i] > max_age:
        return None
    return float(prices[i])


class DerivFeed:
    def __init__(self, url: str = DERIV_WS):
        self.url, self.ws, self.offset_s = url, None, 0.0

    def _call(self, req: dict) -> dict:
        import websocket

        for attempt in range(3):
            try:
                if self.ws is None:
                    self.ws = websocket.create_connection(self.url, timeout=15)
                self.ws.send(json.dumps(req))
                r = json.loads(self.ws.recv())
                if "error" in r:
                    raise RuntimeError(r["error"].get("message", "error de Deriv"))
                return r
            except (OSError, ValueError, websocket.WebSocketException):
                self.ws = None
                time.sleep(1 + attempt)
        raise ConnectionError("Deriv no responde")

    def sync_clock(self) -> float:
        t0 = time.time()
        server = float(self._call({"time": 1})["time"])
        self.offset_s = server - (t0 + time.time()) / 2
        return self.offset_s

    def now(self) -> float:
        return time.time() + self.offset_s

    def candles(self, pair: str, count: int = N_BAND + 2) -> pd.DataFrame:
        r = self._call({"ticks_history": f"frx{pair}", "style": "candles", "granularity": 60, "count": count,
                        "end": "latest"})
        c = pd.DataFrame(r.get("candles", []))
        if c.empty:
            return c
        return c.set_index("epoch")[["open", "high", "low", "close"]].astype(float)

    def ticks(self, pair: str, start: int, end: int) -> tuple[np.ndarray, np.ndarray]:
        r = self._call({"ticks_history": f"frx{pair}", "style": "ticks", "start": start, "end": end, "count": 5000})
        h = r.get("history", {})
        return np.asarray(h.get("times", []), float), np.asarray(h.get("prices", []), float)


class NightLoop:
    def __init__(self, runtime: Path, feed: DerivFeed | None = None, ventana: str = "auto", pairs=PAIRS,
                 sound: bool = True, log=print):
        self.dir = Path(runtime)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.feed = feed or DerivFeed()
        self.ventana = auto_window() if ventana == "auto" else ventana
        self.pairs, self.sound, self.log = tuple(pairs), sound, log
        self.busy: dict[str, int] = {}
        self.started = utcnow()
        self.last: dict = {}
        rows = read_rows(self.dir / "senales.jsonl")[0]
        self.resolved = {r["alert_id"] for r in rows if r.get("evento") == "resultado"}
        self.pending = [r for r in rows if r.get("evento") == "aviso" and r["alert_id"] not in self.resolved]

    def _write(self, row: dict) -> None:
        jsonutil.append_line(self.dir / "senales.jsonl", jsonutil.dumps(row))

    def _beep(self) -> None:
        if self.sound and shutil.which("paplay") and os.path.exists(SOUND):
            subprocess.Popen(["paplay", SOUND], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def step(self, t_epoch: int) -> list[dict]:
        """Decide en la apertura `t_epoch` (múltiplo de 60) de la vela de entrada."""
        t = pd.Timestamp(t_epoch, unit="s", tz="UTC")
        if not in_window(t, self.ventana):
            self.last = {"estado": "fuera de ventana", "minuto": t.isoformat()}
            return []
        out = []
        for pair in self.pairs:
            if self.busy.get(pair, 0) > t_epoch:
                continue
            try:
                c = self.feed.candles(pair)
            except (ConnectionError, RuntimeError) as exc:
                self.log(f"  {pair}: sin datos ({exc})")
                continue
            closed = c[c.index < t_epoch]
            if closed.empty or closed.index[-1] != t_epoch - 60:
                continue  # la vela de la señal no existe o aún no cerró
            idx = closed.index.to_numpy()
            last = closed.iloc[-N_BAND:]
            if len(last) < N_BAND or (np.diff(last.index.to_numpy()) != 60).any():
                continue  # se exigen 20 velas consecutivas
            side = band_side(closed["close"].to_numpy())
            if side == 0:
                continue
            row = {"evento": "aviso", "alert_id": uuid.uuid4().hex[:12], "par": pair,
                   "lado": "CALL" if side > 0 else "PUT", "vela_senal": pd.Timestamp(idx[-1], unit="s", tz="UTC").isoformat(),
                   "entrada_desde": t.isoformat(), "entrar_antes": (t + pd.Timedelta(seconds=LATE_S)).isoformat(),
                   "vencimiento_min": DUR_S // 60, "precio_cierre": float(closed["close"].iloc[-1]),
                   "emitido": pd.Timestamp(self.feed.now(), unit="s", tz="UTC").isoformat(), "ventana": self.ventana}
            self._write(row)
            self.pending.append(row)
            self.busy[pair] = t_epoch + DUR_S
            out.append(row)
            local = t.tz_convert(BOGOTA).strftime("%H:%M")
            self.log(f"{local} Bogotá  {pair[:3]}/{pair[3:]}  {'↑ CALL' if side > 0 else '↓ PUT'}  3 min — entre ya "
                     f"(antes de {LATE_S} s)")
        if out:
            self._beep()
        self.last = {"estado": "señales" if out else "sin señal", "minuto": t.isoformat(), "avisos": len(out)}
        return out

    def resolve(self, now_epoch: float) -> None:
        """Resultado de referencia con los ticks de Deriv: entrada en el clic (o +10 s), salida 180 s después."""
        clicks = {c["alert_id"]: c for c in read_rows(self.dir / "clics.jsonl")[0]}
        still = []
        for r in self.pending:
            t0 = pd.Timestamp(r["entrada_desde"]).timestamp()
            ck = clicks.get(r["alert_id"])
            entry_t = pd.Timestamp(ck["hora_deriv"]).timestamp() if ck else t0 + LAT_DEFAULT_S
            if now_epoch < entry_t + DUR_S + 15:
                still.append(r)
                continue
            try:
                times, prices = self.feed.ticks(r["par"], int(t0) - 120, int(entry_t + DUR_S) + 5)
            except (ConnectionError, RuntimeError):
                still.append(r)
                continue
            e = price_before(times, prices, entry_t)
            x = price_before(times, prices, entry_t + DUR_S)
            res = None if e is None or x is None else (0 if abs(x - e) < 1e-9 else (1 if x > e else -1))
            side = 1 if r["lado"] == "CALL" else -1
            out = {"evento": "resultado", "alert_id": r["alert_id"], "par": r["par"], "entrada_ref": e, "salida_ref": x,
                   "demora_s": round(entry_t - t0, 1), "con_clic": bool(ck),
                   "resultado": None if res is None else ("empate" if res == 0 else ("gana" if res == side else "pierde"))}
            self._write(out)
            self.resolved.add(r["alert_id"])
        self.pending = still

    def write_state(self) -> None:
        state = {"actualizado": utcnow().isoformat(), "inicio": self.started.isoformat(), "ventana": self.ventana,
                 "pares": list(self.pairs), "desfase_reloj_s": self.feed.offset_s, "ultimo": self.last,
                 "pendientes": len(self.pending)}
        tmp = self.dir / f"state.json.{os.getpid()}.tmp"
        tmp.write_text(jsonutil.dumps(state, default=str), encoding="utf-8")
        tmp.replace(self.dir / "state.json")

    def run(self, iterations: int = 0) -> None:
        try:
            self.feed.sync_clock()
        except ConnectionError as exc:
            self.log(f"Aviso: no se pudo sincronizar el reloj con Deriv ({exc}); se usa el del PC")
        self.log(f"Reversión nocturna ({self.ventana}) en {len(self.pairs)} pares. SOLO CUENTA DEMO.")
        n = 0
        while not iterations or n < iterations:
            now = self.feed.now()
            nxt = (int(now) // 60 + 1) * 60
            self.write_state()
            time.sleep(max(0.0, nxt + FIRE_AT_S - self.feed.now()))
            try:
                self.step(nxt)
                self.resolve(self.feed.now())
            except Exception as exc:  # el bucle no se detiene por un fallo puntual de red
                self.log(f"  error en el minuto {datetime.fromtimestamp(nxt, timezone.utc):%H:%M} UTC: {exc}")
            self.write_state()
            n += 1


def diario(runtime: Path) -> list[dict]:
    rows = read_rows(Path(runtime) / "senales.jsonl")[0]
    res = {r["alert_id"]: r for r in rows if r.get("evento") == "resultado"}
    clicks = {c["alert_id"]: c for c in read_rows(Path(runtime) / "clics.jsonl")[0]}
    out = []
    for r in rows:
        if r.get("evento") != "aviso":
            continue
        x = res.get(r["alert_id"], {})
        out.append({**r, "clic": clicks.get(r["alert_id"], {}).get("hora_deriv"), "resultado": x.get("resultado"),
                    "demora_s": x.get("demora_s"), "entrada_ref": x.get("entrada_ref"), "salida_ref": x.get("salida_ref")})
    return out[-200:][::-1]


def resumen(runtime: Path) -> dict:
    d = diario(runtime)
    done = [r for r in d if r["resultado"] in ("gana", "pierde")]
    clic = [r for r in done if r["clic"]]
    w = sum(r["resultado"] == "gana" for r in done)
    wc = sum(r["resultado"] == "gana" for r in clic)
    return {"avisos": len(d), "medidos": len(done), "aciertos": w, "acierto": w / len(done) if done else None,
            "con_clic": len(clic), "acierto_con_clic": wc / len(clic) if clic else None,
            "empates": sum(r["resultado"] == "empate" for r in d)}
