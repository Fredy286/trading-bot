"""Estudio 51 (pre-registro en docs/01): blitz de ETH de IQ Option (3 min desde la compra, pago 86 %) con la receta del
Estudio 42, cambiando BTC por ETH. Buscar más señales vigilando otra moneda.

- Variables: las del Estudio 42, con datos de ETH: vela anterior de Binance, bloque parcial hasta el segundo 50 con
  velas de 1 s (tabla del Estudio 26) y tres variables del compuesto.
- Etiqueta de entrenamiento: compuesto de 3 bolsas (promedio simple de los cierres de 1 min de ETH/USDT en Binance,
  Bybit y OKX).
- Juicio: ese compuesto y, además, el de 4 bolsas con los pesos de BTC del Estudio 47. Los pesos que usa IQ Option
  para ETH no se conocen, así que deben pasar los dos.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import bolsas
from .contracts import BinaryContract
from .experiment import git_sha, jsonable, load_config
from .features import FEATURES, compute_features
from .study3 import load, spot_bars
from .study16 import partial_features
from .study20 import K, TEST_END, TEST_START, evaluate
from .study41 import composite
from .study42 import _walk_forward, comp_features, label3
from .study47 import PRED, WEIGHTS, iq_price

SYMBOL = "ETHUSDT"
PAYOUT, DUR, ALPHA = 0.86, 3, 0.05 / 2
HYPS = {"H51a": None, "H51b": 0.57}  # None = todas las de la política (EV ≥ 0,02)
TAB = Path("data/processed/estudio26/ETHUSDT/tabla.parquet")
M1 = Path("data/processed/estudio26/ETHUSDT/1m")
N_DAYS = 420  # 2025-09-01 → 2026-10-25


def closes(first: str = "2024-08", last: str = "2026-10", gate_first: str = "2025-09") -> dict[str, pd.Series]:
    out = {}
    for v in ("binance", "bybit", "okx", "gate"):
        months = [p.strftime("%Y-%m") for p in pd.period_range(gate_first if v == "gate" else first, last, freq="M")]
        x = pd.concat([bolsas.month_closes(SYMBOL, v, m) for m in months]).sort_index()
        out[v] = x[~x.index.duplicated(keep="last")]
    return out


def minute_bars(root3: Path = Path("data/raw/estudio3")) -> pd.DataFrame:
    """Velas de 1 min de ETH/USDT de Binance: las del Estudio 3 (hasta 2026-08) y las del Estudio 26 (2025-09 → 2026-10)."""
    late = pd.concat([pd.read_parquet(f) for f in sorted(Path(M1).glob("*.parquet"))])
    spot = pd.concat([load(root3, SYMBOL, "spot"), late[["o", "h", "l", "c", "volume", "trades", "taker_buy_base"]]])
    spot = spot[~spot.index.duplicated(keep="last")].sort_index()
    return spot


def btc_signals(margin: float, umbral: float | None) -> pd.DatetimeIndex:
    """Minutos con señal del blitz de BTC (predicciones del Estudio 42, misma política) para medir el solapamiento."""
    P = pd.read_parquet(PRED)
    side = np.where(P["p"] >= 0.5, 1, -1)
    pdir = np.where(side == 1, P["p"], 1 - P["p"])
    take = BinaryContract(PAYOUT, "refund").ev(pdir, P["q"].to_numpy()) >= margin
    if umbral is not None:
        take &= pdir >= umbral
    return P.index[take]


def run(out_dir: Path = Path("results/estudio51"), n_boot: int = 1000, log=print) -> dict:
    cfg = load_config("config/research.toml")  # solo se lee
    margin = cfg["contracts"]["binary_ev_margin"]
    bars = spot_bars(minute_bars())
    data_start = pd.Timestamp(TEST_START, tz="UTC") - pd.DateOffset(months=12) - pd.Timedelta(days=7)
    bars = bars[(bars.index >= data_start) & (bars.index < pd.Timestamp(TEST_END, tz="UTC"))]
    idx = bars.index
    tab = pd.read_parquet(TAB).reindex(idx)
    prev = compute_features(bars).shift(1)  # vela t − 1, ya cerrada en el segundo 50 de t
    vol_prev = np.exp(prev["lvol60"])
    cl = closes()
    comp = composite({v: cl[v] for v in ("binance", "bybit", "okx")})
    iq = iq_price(cl, WEIGHTS)
    X = pd.concat([prev[FEATURES], partial_features(tab, bars["o"], vol_prev, K),
                   comp_features(comp, cl["binance"], vol_prev, idx)], axis=1)
    y, y_iq, y_bn = label3(comp, idx), label3(iq, idx), label3(cl["binance"], idx)
    tie = pd.Series(np.where(np.isnan(y), np.nan, (y == 0).astype(float)), index=idx)
    q_hat = tie.shift(DUR + 2).rolling(1440, min_periods=200).mean().to_numpy()
    ok = X.notna().all(axis=1).to_numpy() & ~np.isnan(q_hat)
    log("Modelo de ETH con la etiqueta del compuesto de 3 bolsas:")
    p = _walk_forward(X, y, ok, idx, cfg, log)
    contract = BinaryContract(PAYOUT, "refund")
    be = 1 / (1 + PAYOUT)
    sel = ~np.isnan(p)
    times = idx[sel]
    rep = {"estudio": "Estudio 51 — blitz de ETH de IQ Option con la receta del Estudio 42 (pre-registro en docs/01)",
           "git_sha": git_sha(), "periodo_prueba": [TEST_START, TEST_END], "pago": PAYOUT, "equilibrio": be,
           "hipotesis": {}, "informativo": {}}
    user_hours = (times.hour >= 2) & (times.hour < 6)  # 21:00–01:00 Bogotá
    side = np.where(p[sel] >= 0.5, 1, -1)
    pmax = np.where(side == 1, p[sel], 1 - p[sel])
    for h, umbral in HYPS.items():
        x = evaluate(p[sel], y[sel], q_hat[sel], times, contract, margin, n_boot, 1 - ALPHA, umbral=umbral)
        xiq = evaluate(p[sel], y_iq[sel], q_hat[sel], times, contract, margin, n_boot, 1 - ALPHA, umbral=umbral)
        crit = {"min_300": x["operaciones"] >= 300, "p_bonferroni": x["p"] < ALPHA, "wilson": x["lo95"] > be,
                "wilson_4_bolsas": xiq["lo95"] > be, "ev_ic": x["ev_ic"][0] > 0, "meses_60": x["meses_ev_positivo"] >= 0.6}
        x.update({"criterios": crit, "pasa": all(crit.values()), "por_dia_calendario": x["operaciones"] / N_DAYS,
                  "juicio_4_bolsas": {k: v for k, v in xiq.items() if k != "mensual"}})
        rep["hipotesis"][h] = x
        take = (contract.ev(pmax, q_hat[sel]) >= margin) & ~np.isnan(y[sel]) & (pmax >= (umbral or 0))
        eth_min = times[take]
        btc_min = btc_signals(margin, umbral)
        both = eth_min.isin(btc_min)
        info = {"horario_usuario": evaluate(np.where(user_hours, p[sel], 0.5), y[sel], q_hat[sel], times, contract,
                                            margin, 200, 0.95, umbral=umbral),
                "juicio_binance": evaluate(p[sel], y_bn[sel], q_hat[sel], times, contract, margin, 200, 0.95,
                                           umbral=umbral),
                "solapamiento_con_btc": {"minutos_eth": int(len(eth_min)), "tambien_btc": int(both.sum()),
                                         "btc_por_dia": len(btc_min) / N_DAYS, "eth_por_dia": len(eth_min) / N_DAYS,
                                         "minutos_con_alguna_por_dia": len(eth_min.union(btc_min)) / N_DAYS}}
        for d in info.values():
            d.pop("mensual", None)
        info["horario_usuario"]["por_noche"] = info["horario_usuario"]["operaciones"] / N_DAYS
        rep["informativo"][h] = info
        log(f"{h}: pasa={x['pasa']} | {x['operaciones']} ops ({x['por_dia_calendario']:.1f}/día), acierto "
            f"{x['acierto']} [{x['lo95']:.4f}] EV {x['ev']:+.4f} | 4 bolsas {xiq['acierto']} [{xiq['lo95']:.4f}] | {crit}")
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"p": p[sel], "y": y[sel], "y_iq": y_iq[sel], "y_bn": y_bn[sel], "q": q_hat[sel]},
                 index=times).to_parquet(out_dir / "predicciones.parquet")
    (out_dir / "resultado.json").write_text(json.dumps(jsonable(rep), indent=2, ensure_ascii=False), encoding="utf-8")
    return rep
