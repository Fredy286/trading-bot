"""Verificación adversaria del Estudio 15 (informativa; no cambia el veredicto de la fase de desarrollo).

1. Alineación: el cierre del segundo 59 de cada minuto debe coincidir con el cierre de la vela de 1 min (si hubiera
   un desfase de un minuto, el bloque nuevo vería el futuro).
2. Etiqueta independiente: la dirección del minuto siguiente recalculada solo con velas de 1 s.
3. Retraso de entrada: acierto y EV de las operaciones de la política B de cada modelo entrando d segundos después
   del cierre de la vela (precio = último negociado antes de cierre + d) y venciendo 60 s después.

Uso: .venv/bin/python scripts/verificacion_estudio15.py → results/estudio15/verificacion.json
"""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

from tradingbot.data.http import get_bytes, make_session
from tradingbot.research.contracts import BinaryContract
from tradingbot.research.study3 import _read_klines, load, spot_bars
from tradingbot.research.study15 import URL

RAIZ = Path(__file__).resolve().parents[1]
CACHE = RAIZ / "data/processed/estudio15/cierres_1s"
DELAYS = (1, 2, 5, 10, 20, 30)
POINT = 0.01


def closes_month(ym: str, session) -> pd.Series:
    f = CACHE / f"{ym}.parquet"
    if f.exists():
        return pd.read_parquet(f)["c"]
    raw = get_bytes(session, URL.format(s="BTCUSDT", ym=ym), timeout=300)
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        sec = _read_klines(zf.read(zf.namelist()[0]))
    s = sec["c"].astype(np.float64)
    s = s[~s.index.duplicated(keep="last")].sort_index()
    f.parent.mkdir(parents=True, exist_ok=True)
    s.to_frame().to_parquet(f)
    print(f"  cierres 1 s {ym}: {len(s):,}", flush=True)
    return s


def main() -> None:
    pred = pd.read_parquet(RAIZ / "data/processed/estudio15/predicciones_dev.parquet")
    months = [p.strftime("%Y-%m") for p in pd.period_range(pred.index.min(), pred.index.max(), freq="M")]
    nxt = (pd.Period(months[-1]) + 1).strftime("%Y-%m")
    session = make_session()
    sec = pd.concat([closes_month(m, session) for m in months + ([nxt] if nxt <= "2025-08" else [])]).sort_index()
    secs = sec.index.as_unit("s").asi8 // 1 if sec.index.unit != "s" else sec.index.asi8
    secs = pd.DatetimeIndex(sec.index).as_unit("ns").asi8 // 10**9
    px = sec.to_numpy()

    def last_before(t_sec: np.ndarray) -> np.ndarray:
        """Último precio negociado antes del segundo t (vela de 1 s que abre en t−1 o antes, máx. 5 s de hueco)."""
        i = np.searchsorted(secs, t_sec - 1, side="right") - 1
        ok = (i >= 0) & ((t_sec - 1) - secs[np.clip(i, 0, None)] <= 5)
        return np.where(ok, px[np.clip(i, 0, None)], np.nan)

    # 1) Alineación con las velas de 1 min.
    bars = spot_bars(load(RAIZ / "data/raw/estudio3", "BTCUSDT", "spot"))
    bars = bars[(bars.index >= pred.index.min()) & (bars.index <= pred.index.max())]
    close_t = (bars.index + pd.Timedelta(minutes=1)).as_unit("ns").asi8 // 10**9
    c59 = last_before(close_t)
    m = ~np.isnan(c59) & bars["c"].notna().to_numpy()
    align = float(np.mean(np.isclose(c59[m], bars["c"].to_numpy()[m], rtol=0, atol=1e-9)))
    shifted = float(np.mean(np.isclose(last_before(close_t - 60)[m], bars["c"].to_numpy()[m], rtol=0, atol=1e-9)))

    # 2) y 3) Resultado con velas de 1 s para cada retraso, en las operaciones de la política B.
    contract = BinaryContract(0.85, "refund")
    t0 = (pred.index + pd.Timedelta(minutes=1)).as_unit("ns").asi8 // 10**9  # cierre de la vela de decisión
    out = {"alineacion_cierre_seg59_igual_cierre_1min": align, "control_desfasado_un_minuto": shifted, "modelos": {}}
    for col in ("p_ref", "p_prueba"):
        p = pred[col].to_numpy()
        side = np.where(p >= 0.5, 1, -1)
        p_dir = np.where(side == 1, p, 1 - p)
        take = contract.ev(p_dir, pred["q"].to_numpy()) >= 0.02
        res = {}
        for d in DELAYS:
            o, c = last_before(t0[take] + d), last_before(t0[take] + d + 60)
            ok = ~np.isnan(o) & ~np.isnan(c)
            mv = np.sign(np.round((c[ok] - o[ok]) / (POINT / 2))) * side[take][ok]
            n, w = int((mv != 0).sum()), int((mv > 0).sum())
            pnl = np.where(mv == 0, 0.0, np.where(mv > 0, 0.85, -1.0))
            res[f"+{d}s"] = {"n": n, "acierto": w / n if n else None, "ev": float(pnl.mean()) if len(pnl) else None}
        # Concordancia de la etiqueta de 1 min (apertura → cierre de t+1) con la de +1 s.
        out["modelos"][col] = {"operaciones": int(take.sum()), "por_retraso": res}
        print(col, json.dumps(res), flush=True)
    dest = RAIZ / "results/estudio15/verificacion.json"
    dest.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("alineacion_cierre_seg59_igual_cierre_1min", "control_desfasado_un_minuto")}))


if __name__ == "__main__":
    main()
