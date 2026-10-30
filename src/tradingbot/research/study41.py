"""Estudio 41 (pre-registro en docs/01, commit 4ae87c4): las señales de H20a juzgadas con el precio que parece usar
IQ Option: el promedio simple de los cierres de 1 min de BTC/USDT al contado de Binance, Bybit y OKX. Mismo diseño que
los Estudios 37 y 38.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
import requests

from .contracts import BinaryContract
from .experiment import git_sha, jsonable
from .study37 import ALPHA, BE, PRED, evaluate

WORK = Path("data/raw/bolsas_usdt")
END = pd.Timestamp("2026-10-26 00:05", tz="UTC")  # las señales terminan el 2026-10-25; lo posterior está reservado
VENUES = ("binance", "bybit", "okx")


def _get(s: requests.Session, url: str, params: dict) -> dict | list:
    for intento in range(6):
        try:
            r = s.get(url, params=params, timeout=30)
            if r.status_code == 200:
                return r.json()
        except requests.RequestException:
            pass
        time.sleep(2 * (intento + 1))  # límite de velocidad u otro fallo temporal
    raise RuntimeError(f"sin respuesta de {url} {params}")


def _ms(t: pd.Timestamp) -> int:
    return int(t.timestamp() * 1000)


def _binance(s, a, b) -> list[tuple[int, float]]:
    k = _get(s, "https://api.binance.com/api/v3/klines",
             {"symbol": "BTCUSDT", "interval": "1m", "startTime": _ms(a), "endTime": _ms(b), "limit": 1000})
    return [(int(x[0]), float(x[4])) for x in k]


def _bybit(s, a, b) -> list[tuple[int, float]]:
    r = _get(s, "https://api.bybit.com/v5/market/kline",
             {"category": "spot", "symbol": "BTCUSDT", "interval": "1", "start": _ms(a), "end": _ms(b), "limit": 1000})
    return [(int(x[0]), float(x[4])) for x in r["result"]["list"]]


def _okx(s, a, b) -> list[tuple[int, float]]:
    # «after» y «before» son exclusivos: velas con ts en [a, b]
    r = _get(s, "https://www.okx.com/api/v5/market/history-candles",
             {"instId": "BTC-USDT", "bar": "1m", "after": _ms(b) + 1, "before": _ms(a) - 1, "limit": 100})
    return [(int(x[0]), float(x[4])) for x in r["data"]]


PAGE = {"binance": (_binance, 1000, 0.05), "bybit": (_bybit, 1000, 0.1), "okx": (_okx, 100, 0.11)}


def pages(start: pd.Timestamp, end: pd.Timestamp, size: int) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    """Ventanas [a, b] de `size` minutos que cubren [start, end) sin solaparse."""
    out, a = [], start
    while a < end:
        b = min(a + pd.Timedelta(minutes=size - 1), end - pd.Timedelta(minutes=1))
        out.append((a, b))
        a = b + pd.Timedelta(minutes=1)
    return out


def month_closes(venue: str, ym: str, work: Path = WORK, session=None) -> pd.Series:
    """Cierres de 1 min de BTC/USDT de una bolsa en el mes `ym` (caché por mes)."""
    f = Path(work) / venue / f"{ym}.parquet"
    if f.exists():
        return pd.read_parquet(f)["c"]
    s = session or requests.Session()
    fetch, size, pause = PAGE[venue]
    start = pd.Timestamp(ym + "-01", tz="UTC")
    end = min(start + pd.offsets.MonthBegin(1), END)
    rows = []
    for a, b in pages(start, end, size):
        rows.extend(r for r in fetch(s, a, b) if _ms(a) <= r[0] <= _ms(b))
        time.sleep(pause)
    df = pd.DataFrame(rows, columns=["t", "c"]).drop_duplicates("t")
    ser = pd.Series(df["c"].to_numpy(), index=pd.to_datetime(df["t"], unit="ms", utc=True)).sort_index()
    f.parent.mkdir(parents=True, exist_ok=True)
    ser.to_frame("c").to_parquet(f)
    print(f"  {venue} {ym}: {len(ser):,} velas", flush=True)
    return ser


def outcome(closes: pd.Series, t: pd.DatetimeIndex) -> np.ndarray:
    """Signo(cierre de la vela t + 1 − cierre de la vela t); 0 si |d| < 0,005; NaN si falta alguna."""
    d = closes.reindex(t + pd.Timedelta(minutes=1)).to_numpy() - closes.reindex(t).to_numpy()
    return np.where(np.isnan(d), np.nan, np.sign(np.where(np.abs(d) < 0.005, 0.0, d)))


def composite(series: dict[str, pd.Series]) -> pd.Series:
    """Promedio simple de los cierres; solo los minutos en que están las tres bolsas."""
    return pd.concat(series, axis=1).dropna().mean(axis=1)


def run(out_dir: Path = Path("results/estudio41"), log=print) -> dict:
    P = pd.read_parquet(PRED)
    side = np.where(P["p"] >= 0.5, 1, -1)
    pdir = np.where(side == 1, P["p"], 1 - P["p"])
    take = (BinaryContract(0.85, "refund").ev(pdir, P["q"].to_numpy()) >= 0.02) & P["y"].notna().to_numpy()
    sig = P[take].assign(side=side[take], pdir=pdir[take])
    months = sorted(set(sig.index.strftime("%Y-%m")))
    s = requests.Session()
    closes = {}
    for v in VENUES:
        x = pd.concat([month_closes(v, m, session=s) for m in months]).sort_index()
        closes[v] = x[~x.index.duplicated(keep="last")]
    closes["compuesto"] = composite({v: closes[v] for v in VENUES})
    res = {k: outcome(c, sig.index) for k, c in closes.items()}
    rep = {"estudio": "Estudio 41 — señales de BTC juzgadas con el promedio de Binance, Bybit y OKX (pre-registro 4ae87c4)",
           "git_sha": git_sha(), "cobertura": {k: [str(c.index.min()), str(c.index.max()), int(len(c))] for k, c in closes.items()},
           "hipotesis": {}, "informativo": {}}
    sd = sig["side"].to_numpy()
    for h, mask in (("H41a", np.ones(len(sig), bool)), ("H41b", sig["pdir"].to_numpy() >= 0.60)):
        x = evaluate(sd[mask], res["compuesto"][mask], sig.index[mask])
        crit = {"min_300": x["operaciones"] >= 300, "p": x["p"] < ALPHA, "wilson": x["lo95"] > BE,
                "meses_60": x["meses_ev_positivo"] >= 0.6}
        x.update({"criterios": crit, "pasa": all(crit.values())})
        rep["hipotesis"][h] = x
        por_bolsa = {k: evaluate(sd[mask], res[k][mask], sig.index[mask])["acierto"] for k in VENUES}
        por_bolsa["binance_predicciones"] = evaluate(sd[mask], sig["y"].to_numpy()[mask], sig.index[mask])["acierto"]
        rep["informativo"][f"{h}_por_bolsa"] = por_bolsa
        log(f"{h}: pasa={x['pasa']} | {x['operaciones']} ops, compuesto {x['acierto']:.4f} [{x['lo95']:.4f}] | "
            + ", ".join(f"{k} {v:.4f}" for k, v in por_bolsa.items()) + f" | {crit}")
    rb, rc = res["binance"], res["compuesto"]
    both = ~np.isnan(rb) & ~np.isnan(rc) & (rb != 0) & (rc != 0)
    agree = rb[both] == rc[both]
    win_b = (sd[both] * rb[both]) > 0
    win_c = (sd[both] * rc[both]) > 0
    rep["informativo"].update({
        "resultado_igual_binance_compuesto": float(agree.mean()),
        "acierto_binance_cuando_no_coinciden": float(win_b[~agree].mean()) if (~agree).any() else None,
        "acierto_compuesto_cuando_no_coinciden": float(win_c[~agree].mean()) if (~agree).any() else None})
    log(f"Binance y compuesto coinciden en {agree.mean():.3f}; cuando no, Binance da la razón al modelo "
        f"{rep['informativo']['acierto_binance_cuando_no_coinciden']:.3f}")
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "resultado.json").write_text(json.dumps(jsonable(rep), indent=2, ensure_ascii=False), encoding="utf-8")
    return rep
