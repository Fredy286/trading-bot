"""Registro diario automático (prueba hacia adelante, sin intervención del usuario).

Cada día, con datos públicos del día anterior, se calcula qué señales habría dado cada estrategia congelada y si
acertaron:
- **BTC 1 min** (modelo congelado H16b, aviso en el segundo 50, clic a +10 s) con las velas de 1 s de Binance;
- **reversión nocturna en divisas** (21–24 UTC, variantes «actual» y «fuerte», clic a +10 s) con los precios
  medios de la API pública de Deriv.

Se guarda un archivo por día en `results/registro/<estrategia>/AAAA-MM-DD.jsonl`. No envía órdenes.

**Sello:** las confirmaciones pre-registradas (Estudios 16, 21 y 29) se evalúan una sola vez, después del 2027-01-18.
Hasta esa fecha `resumen` solo muestra conteos; los aciertos se abren con `abrir=True`, y cada apertura queda anotada.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from ..research.contracts import BinaryContract
from ..research.features import FEATURES, compute_features
from ..research.study3 import spot_bars
from ..research.study16 import label, minute_table, partial_features
from ..timeutil import utcnow
from .anticipada import download_daily, load_bundle, quarter_turn
from .nocturna import LAT_DEFAULT_S, PAIRS, VARIANTES, DerivFeed, band_side, price_before

ROOT = Path("results/registro")
SELLO = pd.Timestamp("2027-01-19", tz="UTC")
CACHE = Path("data/processed/registro")


def _write(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    tmp.replace(path)


# ----------------------------------------------------------------------------------------------------- BTC
def btc_day(day: str, cache: Path = CACHE, bundle: dict | None = None) -> list[dict]:
    """Señales del modelo congelado H16b en el día `day` (UTC) y su resultado con las velas de 1 s de Binance."""
    b = bundle or load_bundle()
    d0 = pd.Timestamp(day, tz="UTC")
    d1 = d0 + pd.Timedelta(days=1)
    m1 = download_daily("1m", f"{d0 - pd.Timedelta(days=3):%Y-%m-%d}", f"{d1:%Y-%m-%d}", cache)
    sec = download_daily("1s", f"{d0:%Y-%m-%d}", f"{d1:%Y-%m-%d}", cache)
    try:  # los 3 primeros minutos del día siguiente cierran las etiquetas de las últimas velas
        nxt = download_daily("1s", f"{d1:%Y-%m-%d}", f"{d1 + pd.Timedelta(days=1):%Y-%m-%d}", cache)
        sec = pd.concat([sec, nxt[nxt.index < d1 + pd.Timedelta(minutes=5)]])
    except FileNotFoundError:
        pass
    bars = spot_bars(m1[~m1.index.duplicated(keep="last")].sort_index())
    minutes = pd.date_range(d0, d1, freq="min", tz="UTC", inclusive="left")
    tab = minute_table(sec, minutes).reindex(bars.index)
    prev = compute_features(bars).shift(1)
    X = pd.concat([prev[FEATURES], partial_features(tab, bars["o"], np.exp(prev["lvol60"]), b["k"])], axis=1)
    X = X[b["features"]]
    day_rows = (bars.index >= d0) & (bars.index < d1) & X.notna().all(axis=1).to_numpy()
    idx = bars.index[day_rows]
    p_up = b["calibrator"].transform(b["model"].predict_proba(X[day_rows].to_numpy())[:, 1])
    y = label(tab, b["k"], b["latencia"])[day_rows]
    side = np.where(p_up >= 0.5, 1, -1)
    p_dir = np.where(side == 1, p_up, 1 - p_up)
    q = np.full(len(p_dir), b["q"])
    ev85 = BinaryContract(0.85, "refund").ev(p_dir, q)
    ev87 = BinaryContract(0.87, "refund").ev(p_dir, q)
    rows = []
    for i in np.flatnonzero(ev85 >= b["ev_margin"]):
        t = idx[i]
        r = None if np.isnan(y[i]) else ("empate" if y[i] == 0 else ("gana" if y[i] == side[i] else "pierde"))
        rows.append({"vela": t.isoformat(), "lado": "CALL" if side[i] > 0 else "PUT", "p": round(float(p_dir[i]), 4),
                     "ev85": round(float(ev85[i]), 4), "ev87": round(float(ev87[i]), 4),
                     "umbral_060": bool(p_dir[i] >= 0.60), "cuarto_hora": bool(quarter_turn(t, 1)),
                     "resultado": r, "modelo": b["model_id"]})
    return rows


# ----------------------------------------------------------------------------------------------- divisas
def night_day(day: str, feed: DerivFeed | None = None, pairs=PAIRS) -> list[dict]:
    """Señales de la reversión nocturna (21–24 UTC del día `day`) con velas y ticks de Deriv, clic a +10 s."""
    f = feed or DerivFeed()
    d0 = pd.Timestamp(day, tz="UTC")
    w0, w1 = d0 + pd.Timedelta(hours=21), d0 + pd.Timedelta(hours=24)
    rows = []
    for pair in pairs:
        r = f._call({"ticks_history": f"frx{pair}", "style": "candles", "granularity": 60, "count": 5000,
                     "start": int((w0 - pd.Timedelta(hours=1)).timestamp()), "end": int(w1.timestamp())})
        c = pd.DataFrame(r.get("candles", []))
        if c.empty:
            continue
        c = c.set_index("epoch")["close"].astype(float)
        # Ticks de toda la ventana en bloques de 15 min (Deriv entrega como mucho 1 000 ticks por petición)
        tt, pp = [], []
        start, stop = int(w0.timestamp()) - 120, int(w1.timestamp()) + max(v[2] for v in VARIANTES.values()) + 30
        for a in range(start, stop, 900):
            ti, pr = f.ticks(pair, a, min(a + 900, stop))
            tt.append(ti)
            pp.append(pr)
        times = np.concatenate(tt) if tt else np.array([])
        order = np.argsort(times, kind="stable")
        times, prices = times[order], (np.concatenate(pp) if pp else np.array([]))[order]
        for var, (n, k, dur) in VARIANTES.items():
            busy = 0
            for t in range(int(w0.timestamp()), int(w1.timestamp()), 60):
                if t < busy:
                    continue
                closed = c[c.index < t]
                if closed.empty or closed.index[-1] != t - 60:
                    continue
                last = closed.iloc[-n:]
                if len(last) < n or (np.diff(last.index.to_numpy()) != 60).any():
                    continue
                side = band_side(closed.to_numpy(), n, k)
                if side == 0:
                    continue
                busy = t + dur
                e_t = t + LAT_DEFAULT_S
                e, x = price_before(times, prices, e_t), price_before(times, prices, e_t + dur)
                res = None if e is None or x is None else (0 if abs(x - e) < 1e-9 else (1 if x > e else -1))
                rows.append({"vela": pd.Timestamp(t, unit="s", tz="UTC").isoformat(), "par": pair, "variante": var,
                             "lado": "CALL" if side > 0 else "PUT", "vencimiento_min": dur // 60,
                             "hora_fuerte": pd.Timestamp(t, unit="s", tz="UTC").hour == 22,
                             "entrada": e, "salida": x,
                             "resultado": None if res is None else ("empate" if res == 0 else
                                                                    ("gana" if res == side else "pierde"))})
    return rows


# --------------------------------------------------------------------------------------------- orquestación
def run_day(day: str, root: Path = ROOT, log=print) -> dict:
    out = {}
    for name, fn in (("btc", btc_day), ("nocturna", night_day)):
        path = Path(root) / name / f"{day}.jsonl"
        if path.exists():
            out[name] = "ya existía"
            continue
        try:
            rows = fn(day)
        except (FileNotFoundError, ConnectionError, RuntimeError) as exc:
            out[name] = f"pendiente ({exc})"
            log(f"{name} {day}: pendiente ({exc})")
            continue
        _write(path, rows)
        out[name] = len(rows)
        log(f"{name} {day}: {len(rows)} señales registradas")
    return out


def run_pending(start: str = "2026-10-26", root: Path = ROOT, log=print) -> dict:
    """Registra todos los días completos desde `start` que aún no tengan archivo."""
    last = (utcnow() - pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    return {d.strftime("%Y-%m-%d"): run_day(d.strftime("%Y-%m-%d"), root, log)
            for d in pd.date_range(start, last, freq="D")}


def _load(root: Path, name: str) -> pd.DataFrame:
    files = sorted((Path(root) / name).glob("*.jsonl"))
    rows = [json.loads(line) for f in files for line in f.read_text(encoding="utf-8").splitlines() if line]
    return pd.DataFrame(rows)


def resumen(root: Path = ROOT, abrir: bool = False, now: pd.Timestamp | None = None) -> dict:
    now = now or pd.Timestamp(utcnow())
    sellado = now < SELLO and not abrir
    out = {"sellado_hasta": SELLO.strftime("%Y-%m-%d") if sellado else None}
    groups = {"btc": [("todas", None), ("p ≥ 0,60", "umbral_060"), ("cuarto de hora", "cuarto_hora")],
              "nocturna": [("actual", ("variante", "actual")), ("fuerte", ("variante", "fuerte")),
                           ("actual, hora fuerte", "hora_fuerte")]}
    for name, specs in groups.items():
        df = _load(root, name)
        out[name] = {"dias": len(list((Path(root) / name).glob("*.jsonl")))}
        for lab, cond in specs:
            g = df
            if isinstance(cond, str) and len(df):
                g = df[df[cond]] if name == "btc" else df[(df[cond]) & (df["variante"] == "actual")]
            elif isinstance(cond, tuple) and len(df):
                g = df[df[cond[0]] == cond[1]]
            n = int(len(g))
            item = {"senales": n}
            if not sellado and n:
                dec = g[g["resultado"].isin(["gana", "pierde"])]
                item["acierto"] = round(float((dec["resultado"] == "gana").mean()), 4) if len(dec) else None
                item["medidas"] = int(len(dec))
            out[name][lab] = item
    if abrir and now < SELLO:
        with open(Path(root) / "aperturas_del_sello.log", "a", encoding="utf-8") as fh:
            fh.write(f"{now.isoformat()} se abrieron los aciertos antes del {SELLO:%Y-%m-%d}\n")
    return out
