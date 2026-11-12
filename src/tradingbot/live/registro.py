"""Registro diario automático (prueba hacia adelante, sin intervención del usuario).

Cada día, con datos públicos del día anterior, se calcula qué señales habría dado cada estrategia congelada y si
acertaron:
- **BTC 1 min** (modelo congelado H16b, aviso en el segundo 50, clic a +10 s) con las velas de 1 s de Binance;
- **reversión nocturna en divisas** (21–24 UTC, variantes «actual» y «fuerte», clic a +10 s) con los precios
  medios de la API pública de Deriv.
- **blitz de BTC de IQ Option** (modelo congelado del Estudio 44, 3 min, pago 86 %) con Binance (archivos diarios),
  Bybit (archivo público de operaciones), OKX (API) y Gate (archivo diario); resultado con el promedio de 3 bolsas y con
  el precio IQ reconstruido (Estudio 47);
- **blitz de ETH** (modelo congelado del Estudio 52), con las mismas fuentes para ETH/USDT.

Se guarda un archivo por día en `results/registro/<estrategia>/AAAA-MM-DD.jsonl`. No envía órdenes.

**Sello:** las confirmaciones pre-registradas (Estudios 16, 21, 29, 44, 46, 52 y 55) se evalúan una sola vez, después del 2027-01-18.
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
def btc_day(day: str, cache: Path = CACHE, bundle: dict | None = None, symbol: str = "BTCUSDT") -> list[dict]:
    """Señales de un modelo congelado con aviso anticipado (BTC H16b por defecto; ETH en `eth_day`) en el día `day`
    (UTC) y su resultado con las velas de 1 s de Binance."""
    b = bundle or load_bundle()
    d0 = pd.Timestamp(day, tz="UTC")
    d1 = d0 + pd.Timedelta(days=1)
    m1 = download_daily("1m", f"{d0 - pd.Timedelta(days=3):%Y-%m-%d}", f"{d1:%Y-%m-%d}", cache, symbol)
    sec = download_daily("1s", f"{d0:%Y-%m-%d}", f"{d1:%Y-%m-%d}", cache, symbol)
    try:  # los 3 primeros minutos del día siguiente cierran las etiquetas de las últimas velas
        nxt = download_daily("1s", f"{d1:%Y-%m-%d}", f"{d1 + pd.Timedelta(days=1):%Y-%m-%d}", cache, symbol)
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


def eth_day(day: str) -> list[dict]:
    """ETH/USDT con su modelo congelado (Estudio 35)."""
    from ..research.study35 import MODEL_PATH, REG_PATH

    return btc_day(day, CACHE / "eth", load_bundle(MODEL_PATH, REG_PATH), "ETHUSDT")


# ----------------------------------------------------------------------------------------------- blitz de IQ Option
# Desde los servidores de GitHub (EE. UU.) la API de Bybit está bloqueada; su archivo público diario de operaciones,
# no. Su último precio de cada minuto coincide con el cierre de sus velas (comprobado el 2026-11-01: 1 440 de 1 440).
BYBIT_URL = "https://public.bybit.com/spot/{s}/{s}_{d}.csv.gz"


def _cached(path: Path, make) -> pd.Series:
    if path.exists():
        return pd.read_parquet(path)["c"]
    s = make()
    path.parent.mkdir(parents=True, exist_ok=True)
    s.to_frame("c").to_parquet(path)
    return s


def bybit_closes(day: pd.Timestamp, cache: Path = CACHE / "blitz", symbol: str = "BTCUSDT") -> pd.Series:
    """Cierres de 1 min al contado de Bybit (BTC/USDT por defecto): último precio de cada minuto de su archivo diario."""
    import gzip
    import io

    from ..data.http import NotFound, get_bytes, make_session

    def make():
        try:
            raw = get_bytes(make_session(), BYBIT_URL.format(s=symbol, d=f"{day:%Y-%m-%d}"), timeout=300)
        except NotFound as exc:
            raise FileNotFoundError(f"Bybit aún no publica el {day:%Y-%m-%d}") from exc
        df = pd.read_csv(io.BytesIO(gzip.decompress(raw)), usecols=["timestamp", "price"])
        s = pd.Series(df["price"].to_numpy(float), index=pd.to_datetime(df["timestamp"], unit="ms", utc=True))
        s = s.sort_index()
        return s.groupby(s.index.floor("min")).last()

    return _cached(Path(cache) / "bybit" / f"{day:%Y-%m-%d}.parquet", make)


def gate_closes(day: pd.Timestamp, cache: Path = CACHE / "blitz", symbol: str = "BTCUSDT") -> pd.Series:
    """Cierres de 1 min de Gate (archivo diario público), para el precio IQ reconstruido (Estudio 47)."""
    from ..data.http import NotFound, get_bytes, make_session
    from ..research.bolsas import GATE_URL
    from ..research.study47 import parse_gate
    from .blitz import NOMBRES

    def make():
        url = GATE_URL.format(ym=f"{day:%Y%m}", pair=NOMBRES[symbol]["gate"], d=f"{day:%Y%m%d}")
        try:
            return parse_gate(get_bytes(make_session(), url, timeout=120))
        except NotFound as exc:
            raise FileNotFoundError(f"Gate aún no publica el {day:%Y-%m-%d}") from exc

    return _cached(Path(cache) / "gate" / f"{day:%Y-%m-%d}.parquet", make)


def okx_closes(a: pd.Timestamp, b: pd.Timestamp, symbol: str = "BTCUSDT") -> pd.Series:
    """Cierres de 1 min de OKX entre a y b (API pública, con reintentos)."""
    import requests

    from ..research.bolsas import _okx
    from ..research.study41 import pages
    from .blitz import NOMBRES

    s, rows = requests.Session(), []
    for x, y in pages(a, b, 100):
        rows.extend(r for r in _okx(s, NOMBRES[symbol]["okx"], x, y)
                    if int(x.timestamp() * 1000) <= r[0] <= int(y.timestamp() * 1000))
    ser = pd.Series(dict(rows), dtype=float).sort_index()
    ser.index = pd.to_datetime(ser.index, unit="ms", utc=True)
    return ser


def _maybe(fn, *args) -> pd.Series:
    try:
        return fn(*args)
    except FileNotFoundError:
        return pd.Series(dtype=float, index=pd.DatetimeIndex([], tz="UTC"))


def blitz_day(day: str, cache: Path = CACHE, symbol: str = "BTCUSDT") -> list[dict]:
    """Blitz de IQ Option (aviso en el segundo 50, 3 min, pago 86 %) con el modelo congelado de cada moneda: BTC
    (Estudio 44) o ETH (Estudio 52). Señales del día y su resultado con el promedio de 3 bolsas (el pre-registrado) y
    con el precio IQ reconstruido (pesos del Estudio 47)."""
    from ..research.study41 import composite
    from ..research.study42 import comp_features, label3
    from ..research.study47 import iq_price
    from .blitz import MODELOS

    b = load_bundle(*MODELOS[symbol])
    bin_cache = Path(cache) if symbol == "BTCUSDT" else Path(cache) / "eth"  # mismos archivos que btc_day / eth_day
    ven_cache = Path(cache) / ("blitz" if symbol == "BTCUSDT" else "blitz_eth")
    d0 = pd.Timestamp(day, tz="UTC")
    d1 = d0 + pd.Timedelta(days=1)
    m1 = download_daily("1m", f"{d0 - pd.Timedelta(days=3):%Y-%m-%d}", f"{d1:%Y-%m-%d}", bin_cache, symbol)
    sec = download_daily("1s", f"{d0:%Y-%m-%d}", f"{d1:%Y-%m-%d}", bin_cache, symbol)
    try:
        nxt = download_daily("1s", f"{d1:%Y-%m-%d}", f"{d1 + pd.Timedelta(days=1):%Y-%m-%d}", bin_cache, symbol)
        sec = pd.concat([sec, nxt[nxt.index < d1 + pd.Timedelta(minutes=6)]])
    except FileNotFoundError:
        pass
    try:  # las últimas velas del día cierran su etiqueta de 3 min en el día siguiente
        m_next = download_daily("1m", f"{d1:%Y-%m-%d}", f"{d1 + pd.Timedelta(days=1):%Y-%m-%d}", bin_cache, symbol)
        m1 = pd.concat([m1, m_next[m_next.index < d1 + pd.Timedelta(minutes=6)]])
    except FileNotFoundError:
        pass
    bars = spot_bars(m1[~m1.index.duplicated(keep="last")].sort_index())
    tab = minute_table(sec, pd.date_range(d0, d1, freq="min", tz="UTC", inclusive="left")).reindex(bars.index)
    prev = compute_features(bars).shift(1)
    vol = np.exp(prev["lvol60"])
    by = pd.concat([bybit_closes(d0 - pd.Timedelta(days=1), ven_cache, symbol), bybit_closes(d0, ven_cache, symbol),
                    _maybe(bybit_closes, d1, ven_cache, symbol)])
    ok = okx_closes(d0 - pd.Timedelta(hours=2), d1 + pd.Timedelta(minutes=5), symbol)
    ga = pd.concat([gate_closes(d0, ven_cache, symbol), _maybe(gate_closes, d1, ven_cache, symbol)])
    bn = bars["c"]
    comp = composite({"binance": bn, "bybit": by[~by.index.duplicated()], "okx": ok})
    X = pd.concat([prev[FEATURES], partial_features(tab, bars["o"], vol, b["k"]), comp_features(comp, bn, vol, bars.index)],
                  axis=1)[b["features"]]
    day_rows = (bars.index >= d0) & (bars.index < d1) & X.notna().all(axis=1).to_numpy()
    idx = bars.index[day_rows]
    p_up = b["calibrator"].transform(b["model"].predict_proba(X[day_rows].to_numpy())[:, 1])
    side = np.where(p_up >= 0.5, 1, -1)
    p_dir = np.where(side == 1, p_up, 1 - p_up)
    ev = BinaryContract(b["payout"], "refund").ev(p_dir, np.full(len(p_dir), b["q"]))
    y3 = label3(comp, idx)
    yiq = label3(iq_price({"binance": bn, "bybit": by[~by.index.duplicated()], "okx": ok, "gate": ga[~ga.index.duplicated()]}), idx)

    def res(y, i):
        return None if np.isnan(y[i]) else ("empate" if y[i] == 0 else ("gana" if y[i] == side[i] else "pierde"))

    return [{"vela": idx[i].isoformat(), "lado": "CALL" if side[i] > 0 else "PUT", "p": round(float(p_dir[i]), 4),
             "ev86": round(float(ev[i]), 4), "p057": bool(p_dir[i] >= 0.57),
             "horario_usuario": bool(2 <= idx[i].hour < 6), "resultado": res(y3, i), "resultado_iq": res(yiq, i),
             "modelo": b["model_id"]} for i in np.flatnonzero(ev >= b["ev_margin"])]


def okx_resultados(symbol: str, d0: pd.Timestamp, d1: pd.Timestamp, session=None, dur: int = 5) -> dict[str, dict]:
    """Resultados oficiales de los contratos de 5 o 15 min de OKX que vencen en [d0, d1] (API pública, página a página)."""
    import requests

    from .okx_eventos import OKX, serie

    s = session or requests.Session()
    out, after = {}, int((d1 + pd.Timedelta(minutes=10)).timestamp() * 1000)
    for _ in range(40):
        r = s.get(OKX + "/api/v5/public/event-contract/markets",
                  params={"seriesId": serie(symbol, dur), "state": "expired", "after": after}, timeout=20).json()
        data = r.get("data") or []
        if not data:
            break
        for x in data:
            if x.get("settleValue"):
                out[x["instId"]] = {"outcome": x["outcome"], "partida": float(x["floorStrike"]),
                                    "liquidacion": float(x["settleValue"]), "vence": int(x["expTime"])}
        oldest = min(int(x["expTime"]) for x in data)
        if oldest <= d0.timestamp() * 1000:
            break
        after = oldest
    return out


def okx_day(day: str, symbol: str = "ETHUSDT", cache: Path = CACHE, dur: int = 5) -> list[dict]:
    """Event contracts de OKX de 5 min (modelo congelado del Estudio 55) o de 15 min (Estudio 60): señales del día
    (decisión en el segundo 50 antes de cada ventana, compra a 0,52 con comisión) y su resultado OFICIAL de OKX."""
    from ..research.study41 import composite
    from ..research.study42 import comp_features
    from .okx_eventos import PRECIO_REF, costo, inst_id, modelos

    b = load_bundle(*modelos(dur)[symbol])
    extra = pd.Timedelta(minutes=b["duracion_min"] + 5)  # la última ventana del día vence después de medianoche
    bin_cache = Path(cache) if symbol == "BTCUSDT" else Path(cache) / "eth"
    ven_cache = Path(cache) / ("blitz" if symbol == "BTCUSDT" else "blitz_eth")
    d0 = pd.Timestamp(day, tz="UTC")
    d1 = d0 + pd.Timedelta(days=1)
    m1 = download_daily("1m", f"{d0 - pd.Timedelta(days=3):%Y-%m-%d}", f"{d1:%Y-%m-%d}", bin_cache, symbol)
    sec = download_daily("1s", f"{d0:%Y-%m-%d}", f"{d1:%Y-%m-%d}", bin_cache, symbol)
    bars = spot_bars(m1[~m1.index.duplicated(keep="last")].sort_index())
    tab = minute_table(sec, pd.date_range(d0, d1, freq="min", tz="UTC", inclusive="left")).reindex(bars.index)
    prev = compute_features(bars).shift(1)
    vol = np.exp(prev["lvol60"])
    by = pd.concat([bybit_closes(d0 - pd.Timedelta(days=1), ven_cache, symbol), bybit_closes(d0, ven_cache, symbol)])
    okc = okx_closes(d0 - pd.Timedelta(hours=2), d1, symbol)
    comp = composite({"binance": bars["c"], "bybit": by[~by.index.duplicated()], "okx": okc[~okc.index.duplicated()]})
    X = pd.concat([prev[FEATURES], partial_features(tab, bars["o"], vol, b["k"]),
                   comp_features(comp, bars["c"], vol, bars.index)], axis=1)[b["features"]]
    grid = ((bars.index.minute + 1) % b["duracion_min"]) == 0
    rows_ok = (bars.index >= d0) & (bars.index < d1) & grid & X.notna().all(axis=1).to_numpy()
    idx = bars.index[rows_ok]
    if not len(idx):
        return []
    p_up = b["calibrator"].transform(b["model"].predict_proba(X[rows_ok].to_numpy())[:, 1])
    side = np.where(p_up >= 0.5, 1, -1)
    p_dir = np.where(side == 1, p_up, 1 - p_up)
    ev = p_dir - costo(PRECIO_REF)
    oficiales = okx_resultados(symbol, d0, d1 + extra, dur=b["duracion_min"])
    take = np.flatnonzero(ev >= 0.02)
    # OKX guarda los contratos vencidos solo unos días: si falta el oficial, se usa la etiqueta reconstruida del
    # Estudio 54 (índice de OKX de 1 min + velas de 1 s de Binance), que coincidió con el oficial en 97,8–100 %.
    recon = np.full(len(idx), np.nan)
    faltan = [i for i in take if inst_id(symbol, idx[i] + pd.Timedelta(minutes=1), b["duracion_min"]) not in oficiales]
    if faltan:
        from ..research.study54 import SIMBOLOS, settle_labels

        ix = okx_index_closes(SIMBOLOS[symbol]["indice"], d0 - pd.Timedelta(minutes=30), d1 + extra)
        try:
            nxt = download_daily("1s", f"{d1:%Y-%m-%d}", f"{d1 + pd.Timedelta(days=1):%Y-%m-%d}", bin_cache, symbol)
            sec2 = pd.concat([sec, nxt[nxt.index < d1 + extra]])
        except FileNotFoundError:
            sec2 = sec
        sec2 = sec2[~sec2.index.duplicated(keep="last")].sort_index()
        recon[faltan] = settle_labels(idx[faltan], b["duracion_min"], ix, bars["c"], sec2.index,
                                      sec2["c"].to_numpy(float))
    out = []
    for i in take:
        ventana = idx[i] + pd.Timedelta(minutes=1)
        inst = inst_id(symbol, ventana, b["duracion_min"])
        r = oficiales.get(inst)
        if r is not None:
            res, fuente = ("gana" if (r["outcome"] == "1") == (side[i] == 1) else "pierde"), "oficial"
        elif not np.isnan(recon[i]):
            res, fuente = ("gana" if recon[i] == side[i] else "pierde"), "reconstruido"
        else:
            res, fuente = None, None
        out.append({"ventana": ventana.isoformat(), "instrumento": inst, "lado": "Up" if side[i] > 0 else "Down",
                    "p": round(float(p_dir[i]), 4), "ev_accion": round(float(ev[i]), 4),
                    "horario_usuario": bool(2 <= ventana.hour < 6), "resultado": res, "fuente": fuente,
                    "partida": r and r["partida"], "liquidacion": r and r["liquidacion"], "modelo": b["model_id"]})
    return out


def okx_index_closes(indice: str, a: pd.Timestamp, b: pd.Timestamp) -> pd.Series:
    """Cierres de 1 min del índice de OKX entre a y b (API pública `history-index-candles`)."""
    import requests

    s, rows, after = requests.Session(), [], int(b.timestamp() * 1000)
    while after > a.timestamp() * 1000:
        r = s.get("https://www.okx.com/api/v5/market/history-index-candles",
                  params={"instId": indice, "bar": "1m", "after": after, "limit": 100}, timeout=20).json()
        data = r.get("data") or []
        if not data:
            break
        rows += [(int(x[0]), float(x[4])) for x in data]
        after = min(int(x[0]) for x in data)
    ser = pd.Series(dict(rows), dtype=float).sort_index()
    ser.index = pd.to_datetime(ser.index, unit="ms", utc=True)
    return ser


def okx_eth_day(day: str) -> list[dict]:
    return okx_day(day, "ETHUSDT")


def okx_btc_day(day: str) -> list[dict]:
    return okx_day(day, "BTCUSDT")


def okx15_eth_day(day: str) -> list[dict]:  # Estudio 60
    return okx_day(day, "ETHUSDT", dur=15)


def okx15_btc_day(day: str) -> list[dict]:
    return okx_day(day, "BTCUSDT", dur=15)


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
def blitz_eth_day(day: str) -> list[dict]:
    """Blitz de ETH (modelo congelado del Estudio 52)."""
    return blitz_day(day, symbol="ETHUSDT")


def run_day(day: str, root: Path = ROOT, log=print) -> dict:
    out = {}
    from .okx_eventos import MODELOS as OKX_MODELOS, MODELOS15 as OKX_MODELOS15

    tareas = [("btc", btc_day), ("eth", eth_day), ("nocturna", night_day), ("blitz", blitz_day),
              ("blitz_eth", blitz_eth_day)]
    for nombre, sym, fn, mods in (("okx_eth", "ETHUSDT", okx_eth_day, OKX_MODELOS),
                                  ("okx_btc", "BTCUSDT", okx_btc_day, OKX_MODELOS),
                                  ("okx15_eth", "ETHUSDT", okx15_eth_day, OKX_MODELOS15),
                                  ("okx15_btc", "BTCUSDT", okx15_btc_day, OKX_MODELOS15)):
        if mods[sym][0].exists():  # solo después de congelar su modelo (Estudios 55 y 60)
            tareas.append((nombre, fn))
    from . import gran_bot

    if gran_bot.CONFIG.exists() and all(mp.exists() for mp, _ in gran_bot.bases().values()):  # Estudio 64
        tareas.append(("gran5", gran_bot.gran5_day))
    for name, fn in tareas:
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
              "eth": [("todas", None), ("p ≥ 0,60", "umbral_060")],
              "nocturna": [("actual", ("variante", "actual")), ("fuerte", ("variante", "fuerte")),
                           ("actual, hora fuerte", "hora_fuerte")],
              "blitz": [("todas", None), ("p ≥ 0,57", "p057"), ("horario del usuario", "horario_usuario")],
              "blitz_eth": [("todas", None), ("p ≥ 0,57", "p057"), ("horario del usuario", "horario_usuario")],
              "okx_eth": [("todas", None), ("horario del usuario", "horario_usuario")],
              "okx_btc": [("todas", None), ("horario del usuario", "horario_usuario")],
              "okx15_eth": [("todas", None), ("horario del usuario", "horario_usuario")],
              "okx15_btc": [("todas", None), ("horario del usuario", "horario_usuario")]}
    for name, specs in groups.items():
        df = _load(root, name)
        out[name] = {"dias": len(list((Path(root) / name).glob("*.jsonl")))}
        for lab, cond in specs:
            g = df
            if isinstance(cond, str) and len(df):
                g = (df[df[cond]] if name in ("btc", "eth", "blitz", "blitz_eth", "okx_eth", "okx_btc", "okx15_eth",
                                              "okx15_btc")
                     else df[(df[cond]) & (df["variante"] == "actual")])
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
