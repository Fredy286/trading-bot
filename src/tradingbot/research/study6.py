"""Estudio 6 (pre-registro en docs/01, commit bc97dc0): ¿las «zonas» de precio predicen a 15 min con 1 min
de anticipación?

Para BTC/USDT (contado de Binance) y EUR/USD (HistData M1 BID) se compara, en las MISMAS decisiones y con
el walk-forward de la sección 8, el `logit` de precio frente al mismo `logit` con un bloque fijo de 10
variables de zonas: número redondo, máximo y mínimo del día anterior, extremos de 240 min y sus toques, y
posición del cierre en el rango de 15 min. Mismo diseño y criterios que el Estudio 3 (`study3.compare`).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from ..data import store
from ..data.clean import to_canonical
from ..instruments import get_instrument
from .experiment import git_sha, jsonable, load_config
from .labels import decision_mask
from .study3 import DATA_START, DEV_END, DEV_TEST_START, HORIZON, compare, load, spot_bars, verdict

ZONE_FEATURES = ["z_rn", "z_rn_x15", "z_rn_n", "z_pdh", "z_pdl", "z_hi240", "z_lo240", "z_t_hi", "z_t_lo",
                 "z_rej15"]
STEP = {"BTCUSDT": 1000.0, "EURUSD": 0.0100}  # número redondo (pre-registro)
SOURCE = {"BTCUSDT": "binance (contado, data/raw/estudio3)", "EURUSD": "histdata (M1 BID)"}
WIN = 225  # velas t−239 … t−15
EPS = 1e-9  # tolerancia de redondeo al dividir por el paso (1,1000 / 0,01 = 110,00000000000001)


def zone_features(bars: pd.DataFrame, step: float, rows: np.ndarray | None = None) -> pd.DataFrame:
    """Bloque fijo del pre-registro. Fila t = velas hasta el CIERRE de t (causal).

    Los toques (`z_t_hi`, `z_t_lo`) se calculan solo en las filas `rows` (las de decisión), porque piden
    comparar cada ventana con la σ de su fila; en el resto quedan NaN.
    """
    c, h, l = bars["c"], bars["h"], bars["l"]
    logc, logh, logl = np.log(c), np.log(h), np.log(l)
    lr = logc.diff()
    vol60 = lr.rolling(60, min_periods=50).std()  # igual que compute_features
    sig = (vol60 * np.sqrt(15)).where(vol60 > 0)
    f = pd.DataFrame(index=bars.index)
    r = (c / step).round() * step
    f["z_rn"] = (logc - np.log(r)) / sig
    k = np.floor(c / step + EPS)
    f["z_rn_x15"] = np.sign(k - k.shift(15))
    # Toque: el intervalo [l, h] contiene un múltiplo del paso.
    touch = (np.ceil(l / step - EPS) * step <= h * (1 + EPS)).to_numpy()
    pos = np.arange(len(bars), dtype=float)
    last = pd.Series(np.where(touch, pos, np.nan)).ffill().to_numpy()
    f["z_rn_n"] = np.minimum(np.nan_to_num(pos - last, nan=240.0), 240.0)
    # Día UTC anterior completo (≥ 720 velas con precio).
    day = bars.index.floor("D")
    daily = pd.DataFrame({"h": h, "l": l, "n": c.notna()}).groupby(day).agg({"h": "max", "l": "min", "n": "sum"})
    daily = daily[daily["n"] >= 720]
    prev = day - pd.Timedelta(days=1)
    f["z_pdh"] = (logc - np.log(daily["h"].reindex(prev).to_numpy())) / sig
    f["z_pdl"] = (logc - np.log(daily["l"].reindex(prev).to_numpy())) / sig
    # Extremos de las velas t−239 … t−15 (mínimo 200 con precio, como vol240 en compute_features).
    hi = h.shift(15).rolling(WIN, min_periods=200).max()
    lo = l.shift(15).rolling(WIN, min_periods=200).min()
    f["z_hi240"] = (logc - np.log(hi)) / sig
    f["z_lo240"] = (logc - np.log(lo)) / sig
    f["z_t_hi"], f["z_t_lo"] = np.nan, np.nan
    rows = np.flatnonzero(np.ones(len(bars), bool)) if rows is None else np.asarray(rows)
    rows = rows[rows >= 239]
    lh, ll = logh.to_numpy(), logl.to_numpy()
    lhi, llo, s = np.log(hi.to_numpy()), np.log(lo.to_numpy()), sig.to_numpy()
    th, tl = np.full(len(bars), np.nan), np.full(len(bars), np.nan)
    if len(rows):
        swh = np.lib.stride_tricks.sliding_window_view(lh, WIN)  # ventana i = velas i … i+224
        swl = np.lib.stride_tricks.sliding_window_view(ll, WIN)
    for a in range(0, len(rows), 20_000):
        rr = rows[a:a + 20_000]
        wh, wl = swh[rr - 239], swl[rr - 239]
        with np.errstate(invalid="ignore"):
            th[rr] = np.sum(wh >= (lhi[rr] - 0.25 * s[rr])[:, None], axis=1)
            tl[rr] = np.sum(wl <= (llo[rr] + 0.25 * s[rr])[:, None], axis=1)
    ok = ~np.isnan(lhi) & ~np.isnan(s)
    f["z_t_hi"] = np.where(ok, th, np.nan)
    f["z_t_lo"] = np.where(~np.isnan(llo) & ~np.isnan(s), tl, np.nan)
    h15 = h.rolling(15, min_periods=12).max()
    l15 = l.rolling(15, min_periods=12).min()
    rng = h15 - l15
    f["z_rej15"] = ((c - l15) / rng.where(rng > 0)).where(rng > 0, 0.5).where(h15.notna())
    f.loc[c.isna()] = np.nan
    return f[ZONE_FEATURES].replace([np.inf, -np.inf], np.nan)


def load_bars(symbol: str, root3: Path, root: Path) -> pd.DataFrame:
    if symbol == "BTCUSDT":
        bars = spot_bars(load(root3, symbol, "spot"))
    else:  # EUR/USD: la fuente de la Fase 1B (Enmienda 1); HistData omite minutos sin ticks
        bars, _ = to_canonical(store.load(root, get_instrument(symbol), source="histdata"), fill_gaps=True)
    return bars[(bars.index >= pd.Timestamp(DATA_START, tz="UTC")) & (bars.index < pd.Timestamp(DEV_END, tz="UTC"))]


def run(root3: Path = Path("data/raw/estudio3"), root: Path = Path("data/raw"),
        out_dir: Path = Path("results/estudio6"), n_boot: int = 1000, log=print) -> dict:
    cfg = load_config("config/research.toml")  # solo se lee: mismo walk-forward y ejecución
    res = {}
    for s in STEP:
        bars = load_bars(s, root3, root)
        zf = zone_features(bars, STEP[s], rows=np.flatnonzero(decision_mask(bars.index, HORIZON)))
        log(f"[{s}] velas: {len(bars):,}; filas de decisión con todas las zonas: "
            f"{int(zf.notna().all(axis=1).sum()):,}")
        res[s] = compare(s, bars, zf, cfg, n_boot, log, DEV_TEST_START, DEV_END)
        res[s]["fuente"] = SOURCE[s]
    v = verdict(res)
    report = {"estudio": "Estudio 6 — fase de desarrollo (pre-registro bc97dc0)", "git_sha": git_sha(),
              "horizonte_min": HORIZON, "retraso_entrada": 2, "politica": "B (EV ≥ 0,02)",
              "periodo_prueba": [DEV_TEST_START, DEV_END], "bloque": ZONE_FEATURES, "paso_redondo": STEP,
              "resultados": res, "veredicto": v, "pasa_alguna": any(x["pasa"] for x in v.values())}
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "dev.json").write_text(json.dumps(jsonable(report), indent=2, ensure_ascii=False), encoding="utf-8")
    return report
