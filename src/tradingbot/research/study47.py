"""Estudio 47 (pre-registro en docs/01, commit 452c223): las predicciones de desarrollo del blitz (Estudio 42) juzgadas
con el precio reconstruido de IQ Option. Es un promedio con pesos de los cierres de 1 min de Binance, Bybit, OKX y Gate;
los pesos se ajustaron a 275 velas leídas en capturas del usuario. Gate llega de sus archivos diarios públicos.
"""

from __future__ import annotations

import gzip
import io
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
import requests

from .contracts import BinaryContract
from .experiment import git_sha, jsonable, load_config
from .study20 import evaluate
from .study41 import END, WORK, month_closes
from .study42 import ALPHA, DUR, PAYOUT, label3

WEIGHTS = {"binance": 0.336, "bybit": 0.071, "okx": 0.223, "gate": 0.370}
GATE_URL = "https://download.gatedata.org/spot/candlesticks_1m/{ym}/BTC_USDT-{d}.csv.gz"
PRED = Path("results/estudio42/predicciones.parquet")
MONTHS = tuple(p.strftime("%Y-%m") for p in pd.period_range("2025-09", "2026-10", freq="M"))


def parse_gate(raw: bytes) -> pd.Series:
    """Archivo diario de Gate: tiempo (s), volumen, cierre, máximo, mínimo, apertura."""
    df = pd.read_csv(io.BytesIO(gzip.decompress(raw)), header=None, names=["t", "v", "c", "h", "l", "o"])
    return pd.Series(df["c"].astype(float).to_numpy(), index=pd.to_datetime(df["t"], unit="s", utc=True)).sort_index()


def gate_month(ym: str, work: Path = WORK, session=None) -> pd.Series:
    f = Path(work) / "gate" / f"{ym}.parquet"
    if f.exists():
        return pd.read_parquet(f)["c"]
    s = session or requests.Session()
    start = pd.Timestamp(ym + "-01", tz="UTC")
    end = min(start + pd.offsets.MonthBegin(1), END.floor("D") + pd.Timedelta(days=1))
    parts = []
    for d in pd.date_range(start, end, freq="D", inclusive="left"):
        for intento in range(5):
            r = s.get(GATE_URL.format(ym=f"{d:%Y%m}", d=f"{d:%Y%m%d}"), timeout=60)
            if r.status_code == 200:
                parts.append(parse_gate(r.content))
                break
            time.sleep(2 * (intento + 1))
        time.sleep(0.05)
    ser = pd.concat(parts).sort_index() if parts else pd.Series(dtype=float)
    ser = ser[~ser.index.duplicated(keep="last")]
    ser = ser[ser.index < END]
    f.parent.mkdir(parents=True, exist_ok=True)
    ser.to_frame("c").to_parquet(f)
    print(f"  gate {ym}: {len(ser):,} velas", flush=True)
    return ser


def iq_price(closes: dict[str, pd.Series], weights: dict[str, float] = WEIGHTS) -> pd.Series:
    """Promedio con pesos; solo los minutos en que están todas las bolsas."""
    df = pd.concat({v: closes[v] for v in weights}, axis=1).dropna()
    return sum(df[v] * w for v, w in weights.items()) / sum(weights.values())


def run(out_dir: Path = Path("results/estudio47"), n_boot: int = 1000, log=print) -> dict:
    margin = load_config("config/research.toml")["contracts"]["binary_ev_margin"]
    P = pd.read_parquet(PRED)
    cl = {v: pd.concat([month_closes(v, m) for m in MONTHS]).sort_index() for v in ("binance", "bybit", "okx")}
    s = requests.Session()
    cl["gate"] = pd.concat([gate_month(m, session=s) for m in MONTHS]).sort_index()
    cl = {v: x[~x.index.duplicated(keep="last")] for v, x in cl.items()}
    iq = iq_price(cl)
    three = pd.concat({v: cl[v] for v in ("binance", "bybit", "okx")}, axis=1).dropna().mean(axis=1)
    t = P.index
    y_iq, y3 = label3(iq, t), label3(three, t)
    contract = BinaryContract(PAYOUT, "refund")
    be = 1 / (1 + PAYOUT)
    rep = {"estudio": "Estudio 47 — el blitz juzgado con el precio reconstruido de IQ Option (pre-registro 452c223)",
           "git_sha": git_sha(), "pesos": WEIGHTS, "equilibrio": be,
           "cobertura_gate": [str(cl["gate"].index.min()), str(cl["gate"].index.max()), int(len(cl["gate"]))]}
    x = evaluate(P["p"].to_numpy(), y_iq, P["q"].to_numpy(), t, contract, margin, n_boot, 1 - ALPHA)
    crit = {"min_300": x["operaciones"] >= 300, "p": x["p"] < ALPHA, "wilson": x["lo95"] > be,
            "ev_ic": x["ev_ic"][0] > 0, "meses_60": x["meses_ev_positivo"] >= 0.6}
    x.update({"criterios": crit, "pasa": all(crit.values())})
    rep["H47a"] = x
    user = (t.hour >= 2) & (t.hour < 6)
    info = {"p>=0.57": evaluate(P["p"].to_numpy(), y_iq, P["q"].to_numpy(), t, contract, margin, 200, 0.95, umbral=0.57),
            "horario_usuario": evaluate(np.where(user, P["p"], 0.5), y_iq, P["q"].to_numpy(), t, contract, margin, 200,
                                        0.95),
            "mismo_juicio_con_3_bolsas": evaluate(P["p"].to_numpy(), y3, P["q"].to_numpy(), t, contract, margin, 200,
                                                  0.95)}
    for d in info.values():
        d.pop("mensual")
    both = ~np.isnan(y_iq) & ~np.isnan(y3) & (y_iq != 0) & (y3 != 0)
    info["coincidencia_resultado_iq_vs_3_bolsas"] = float((y_iq[both] == y3[both]).mean())
    rep["informativo"] = info
    log(f"H47a: pasa={x['pasa']} | {x['operaciones']} ops, acierto {x['acierto']:.4f} [{x['lo95']:.4f}] "
        f"EV {x['ev']:+.4f} {x['ev_ic']} | {crit}")
    log("   " + " | ".join(f"{k}: {v['operaciones']} ops, {v['acierto'] and round(v['acierto'], 4)}"
                           for k, v in info.items() if isinstance(v, dict))
        + f" | coincidencia {info['coincidencia_resultado_iq_vs_3_bolsas']:.4f}")
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "resultado.json").write_text(json.dumps(jsonable(rep), indent=2, ensure_ascii=False), encoding="utf-8")
    return rep


# ----------------------------------------------------------------------------------------------- demora del clic
LAGS = (0, 5, 10, 15, 20, 30)
SEC_DIRS = (Path("data/processed/estudio16/seg"), Path("data/processed/senal/seg"))
SEC_DAILY = Path("data/processed/senal/diario/1s")


def _ns(x) -> np.ndarray:
    """Nanosegundos explícitos (pandas 3 guarda microsegundos; registro de errores, ítem 44)."""
    return pd.DatetimeIndex(x).as_unit("ns").asi8


def last_before(sec_index, sec_close, T, max_gap_s: int = 5) -> np.ndarray:
    """Último precio de Binance antes del instante T (vela de 1 s que abre como mucho en T − 1 s)."""
    si, target = _ns(sec_index), _ns(T) - 10**9
    i = np.searchsorted(si, target, side="right") - 1
    ok = (i >= 0) & ((target - si[np.maximum(i, 0)]) <= max_gap_s * 10**9)
    return np.where(ok, np.asarray(sec_close, float)[np.maximum(i, 0)], np.nan)


def iq_at(T: np.ndarray, sec_index, sec_close, basis: pd.Series) -> np.ndarray:
    """Precio IQ reconstruido en el instante T: Binance al segundo menos la diferencia Binance − IQ, interpolada en
    línea recta entre los cierres de minuto (exacta en cada cierre)."""
    Tm = pd.DatetimeIndex(T)
    m0 = (Tm - pd.Timedelta(seconds=60)).floor("min")  # el cierre de m0 cae en m0 + 60 s ≤ T
    b0 = basis.reindex(m0).to_numpy()
    b1 = basis.reindex(m0 + pd.Timedelta(minutes=1)).to_numpy()
    frac = ((Tm - (m0 + pd.Timedelta(seconds=60))) / pd.Timedelta(seconds=60)).to_numpy()
    b = np.where(frac == 0, b0, b0 + (b1 - b0) * frac)
    return last_before(sec_index, sec_close, T) - b


def _seconds_for(month: str) -> pd.Series:
    files = [d / f"{month}.parquet" for d in SEC_DIRS if (d / f"{month}.parquet").exists()]
    if files:
        return pd.read_parquet(files[-1])["c"]
    days = sorted(SEC_DAILY.glob(f"{month}-*.parquet"))
    return pd.concat([pd.read_parquet(f)["c"] for f in days]) if days else pd.Series(dtype=float)


def latency(out_dir: Path = Path("results/estudio47"), lags=LAGS, log=print) -> dict:
    """Nota del blitz: acierto de la política de H42a si el clic llega L s después del cierre de la vela."""
    margin = load_config("config/research.toml")["contracts"]["binary_ev_margin"]
    contract = BinaryContract(PAYOUT, "refund")
    P = pd.read_parquet(PRED)
    side = np.where(P["p"] >= 0.5, 1, -1)
    pdir = np.where(side == 1, P["p"], 1 - P["p"])
    take = contract.ev(pdir, P["q"].to_numpy()) >= margin
    sig = P[take].assign(side=side[take])
    cl = {v: pd.concat([month_closes(v, m) for m in MONTHS]).sort_index() for v in ("binance", "bybit", "okx")}
    cl["gate"] = pd.concat([gate_month(m) for m in MONTHS]).sort_index()
    cl = {v: x[~x.index.duplicated(keep="last")] for v, x in cl.items()}
    basis = (cl["binance"] - iq_price(cl)).dropna()
    res = {L: np.full(len(sig), np.nan) for L in lags}
    for k, m in enumerate(MONTHS):
        rows = np.flatnonzero(sig.index.strftime("%Y-%m") == m)
        if not len(rows):
            continue
        nxt = MONTHS[k + 1] if k + 1 < len(MONTHS) else None
        sec = pd.concat([_seconds_for(m)] + ([_seconds_for(nxt).iloc[:7200]] if nxt else [])).sort_index()
        sec = sec[~sec.index.duplicated(keep="last")]
        si, sc = sec.index, sec.to_numpy()
        t = sig.index[rows]
        for L in lags:
            t_in = (t + pd.Timedelta(seconds=60 + L)).to_numpy()
            t_out = (t + pd.Timedelta(seconds=240 + L)).to_numpy()
            d = iq_at(t_out, si, sc, basis) - iq_at(t_in, si, sc, basis)
            res[L][rows] = np.where(np.isnan(d), np.nan, np.sign(np.where(np.abs(d) < 0.005, 0.0, d)))
        log(f"  {m}: {len(rows)} operaciones")
    from .metrics import wilson
    out = {}
    for L in lags:
        r = sig["side"].to_numpy() * res[L]
        m = ~np.isnan(r)
        n, w = int((r[m] != 0).sum()), int((r[m] > 0).sum())
        lo, _ = wilson(w, n)
        pnl = np.where(r[m] == 0, 0.0, np.where(r[m] > 0, PAYOUT, -1.0))
        out[f"L={L}s"] = {"operaciones": int(m.sum()), "acierto": w / n if n else None, "lo95": float(lo),
                          "ev": float(pnl.mean()) if len(pnl) else None, "limite_desde_el_aviso_s": 10 + L}
        log(f"L = {L:2d} s (clic {10 + L} s después del aviso): {out[f'L={L}s']['operaciones']} ops, "
            f"acierto {out[f'L={L}s']['acierto']:.4f} [{lo:.4f}], EV {out[f'L={L}s']['ev']:+.4f}")
    be = 1 / (1 + PAYOUT)
    control_ok = abs(out["L=0s"]["acierto"] - 0.5532) <= 0.001
    ok = [L for L in lags if out[f"L={L}s"]["lo95"] > be]
    rep = {"nota": "Nota del blitz: cuánto puede tardar el clic (regla fijada antes de calcular, commit e677375)",
           "git_sha": git_sha(), "equilibrio": be, "por_demora": out, "control_L0_reproduce_55_32": control_ok,
           "limite_tarde_s": (10 + max(ok)) if (control_ok and ok) else None}
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    (Path(out_dir) / "latencia.json").write_text(json.dumps(jsonable(rep), indent=2, ensure_ascii=False), encoding="utf-8")
    log(f"control L = 0 reproduce el 55,32 %: {control_ok} → nuevo límite TARDE: {rep['limite_tarde_s']} s")
    return rep
