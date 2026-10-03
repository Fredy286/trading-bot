"""Estudio 3 (pre-registro en docs/01, commit 9bf123a): ¿la información nueva predice a 15 min con 1 min
de anticipación?

Para BTC/USDT y ETH/USDT se compara, en las MISMAS decisiones y con el walk-forward de la sección 8, un
`logit` con solo las variables de precio (referencia) frente al mismo `logit` con un bloque fijo de 17
variables nuevas: flujo agresor de contado y del perpetuo, prima y financiación del perpetuo, y el otro
activo. Entrada 1 minuto después de la señal (etiquetas con retraso 2), política B, binaria 85 %.
"""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

from ..data.clean import to_canonical
from ..data.http import NotFound, get_bytes, make_session
from ..instruments import get_instrument
from .calibration import Calibrator
from .contracts import BinaryContract
from .experiment import git_sha, jsonable, load_config, summarize
from .features import FEATURES, compute_features
from .labels import decision_mask, make_labels
from .metrics import block_bootstrap_mean, wilson
from .models import fit_predict_proba
from .simulate import ExecParams, max_age_for_horizon, simulate
from .walkforward import make_folds

BASE = "https://data.binance.vision/data"
PATHS = {
    "spot": "spot/monthly/klines/{s}/1m/{s}-1m-{ym}.zip",
    "perp": "futures/um/monthly/klines/{s}/1m/{s}-1m-{ym}.zip",
    "prem": "futures/um/monthly/premiumIndexKlines/{s}/1m/{s}-1m-{ym}.zip",
    "fund": "futures/um/monthly/fundingRate/{s}/{s}-fundingRate-{ym}.zip",
}
SYMBOLS = ("BTCUSDT", "ETHUSDT")
OTHER = {"BTCUSDT": "ETHUSDT", "ETHUSDT": "BTCUSDT"}
HORIZON, ENTRY_DELAY = 15, 2
DEV_TEST_START, DEV_END = "2022-01-01", "2025-09-01"  # mismo walk-forward que la sección 8
DATA_START = "2021-01-01"
NEW_FEATURES = ["tib_s_5", "tib_s_15", "tib_s_60", "tib_s_240", "tib_p_5", "tib_p_15", "tib_p_60", "tib_p_240",
                "tib_d_15", "tib_d_60", "prem_c", "prem_d15", "prem_d60", "fund", "x_r5", "x_r15", "x_r60",
                "x_rel15", "x_rel60"]
# La tabla del pre-registro enumera estas 19 variables por nombre; el texto decía «17» por un error de
# conteo (registro de errores, ítem 38). Se usan las 19 de la tabla, que es la lista explícita.


def _months(start: str, end: str) -> list[str]:
    return [p.strftime("%Y-%m") for p in pd.period_range(start, end, freq="M")]


def _read_klines(csv: bytes) -> pd.DataFrame:
    df = pd.read_csv(io.BytesIO(csv), header=None, usecols=[0, 1, 2, 3, 4, 5, 8, 9],
                     names=["open_time", "o", "h", "l", "c", "volume", "trades", "taker_buy_base"])
    if not str(df.iloc[0, 0]).strip().lstrip("-").isdigit():  # archivo con cabecera
        df = df.iloc[1:]
    ot = pd.to_numeric(df["open_time"]).astype(np.int64)
    unit = "us" if ot.max() > 10**14 else "ms"
    idx = pd.DatetimeIndex(pd.to_datetime(ot, unit=unit, utc=True), name="time")
    return pd.DataFrame({c: pd.to_numeric(df[c]).to_numpy(float) for c in df.columns if c != "open_time"}, index=idx)


def _read_funding(csv: bytes) -> pd.DataFrame:
    df = pd.read_csv(io.BytesIO(csv))
    ct = pd.to_numeric(df["calc_time"]).astype(np.int64)
    unit = "us" if ct.max() > 10**14 else "ms"
    return pd.DataFrame({"fund": pd.to_numeric(df["last_funding_rate"]).to_numpy(float)},
                        index=pd.DatetimeIndex(pd.to_datetime(ct, unit=unit, utc=True), name="time"))


def download(root: Path, start: str = "2020-12", end: str = "2025-08", symbols=SYMBOLS, progress: bool = True) -> None:
    """Descarga mensual con caché (data/raw/estudio3/<símbolo>/<tipo>/<AAAA-MM>.parquet)."""
    session = make_session()
    for s in symbols:
        for kind, pattern in PATHS.items():
            for ym in _months(start, end):
                f = Path(root) / s / kind / f"{ym}.parquet"
                if f.exists():
                    continue
                try:
                    raw = get_bytes(session, f"{BASE}/{pattern.format(s=s, ym=ym)}", timeout=120)
                except NotFound:
                    if progress:
                        print(f"  {s} {kind} {ym}: no disponible (404)", flush=True)
                    continue
                with zipfile.ZipFile(io.BytesIO(raw)) as zf:
                    csv = zf.read(zf.namelist()[0])
                part = _read_funding(csv) if kind == "fund" else _read_klines(csv)
                f.parent.mkdir(parents=True, exist_ok=True)
                part.to_parquet(f)
                if progress:
                    print(f"  {s} {kind} {ym}: {len(part):,} filas", flush=True)


def load(root: Path, symbol: str, kind: str) -> pd.DataFrame:
    parts = [pd.read_parquet(f) for f in sorted((Path(root) / symbol / kind).glob("*.parquet"))]
    out = pd.concat(parts).sort_index()
    return out[~out.index.duplicated(keep="last")]


def spot_bars(spot: pd.DataFrame) -> pd.DataFrame:
    """Velas canónicas del contado (precio negociado: bid = ask), como `data/binance.py`."""
    raw = pd.DataFrame(index=spot.index)
    for side in ("bid", "ask"):
        for k in ("o", "h", "l", "c"):
            raw[f"{side}_{k}"] = spot[k]
    raw["bid_v"], raw["ask_v"], raw["trades"] = spot["volume"], 0.0, spot["trades"]
    return to_canonical(raw)[0]


def _imbalance(df: pd.DataFrame, k: int) -> pd.Series:
    buy = df["taker_buy_base"].rolling(k, min_periods=k).sum()
    vol = df["volume"].rolling(k, min_periods=k).sum()
    return (2 * buy / vol.where(vol > 0) - 1)


def new_features(idx: pd.DatetimeIndex, spot: pd.DataFrame, perp: pd.DataFrame, prem: pd.DataFrame,
                 fund: pd.DataFrame, other_spot: pd.DataFrame) -> pd.DataFrame:
    """Bloque fijo del pre-registro. Fila t = información hasta el CIERRE de la vela t (causal)."""
    grid = pd.date_range(idx[0], idx[-1], freq="min").as_unit("ns")
    ns = lambda df: df.set_axis(df.index.as_unit("ns"))  # noqa: E731 — misma resolución para alinear
    spot, perp, prem, other_spot = ns(spot), ns(perp), ns(prem), ns(other_spot)
    sp, pp = spot.reindex(grid), perp.reindex(grid)  # un minuto ausente deja NaN en sus ventanas
    f = pd.DataFrame(index=grid)
    for k in (5, 15, 60, 240):
        f[f"tib_s_{k}"] = _imbalance(sp, k)
        f[f"tib_p_{k}"] = _imbalance(pp, k)
    f["tib_d_15"] = f["tib_p_15"] - f["tib_s_15"]
    f["tib_d_60"] = f["tib_p_60"] - f["tib_s_60"]
    pc = prem["c"].reindex(grid)
    f["prem_c"], f["prem_d15"], f["prem_d60"] = pc, pc - pc.shift(15), pc - pc.shift(60)
    # Financiación: última liquidada con calc_time ≤ cierre de la vela (apertura + 1 min).
    close = pd.DataFrame({"close": grid + pd.Timedelta(minutes=1)})
    fr = fund.reset_index().rename(columns={"time": "calc_time"}).sort_values("calc_time")
    fr["calc_time"] = fr["calc_time"].dt.as_unit("ns")
    f["fund"] = pd.merge_asof(close, fr, left_on="close", right_on="calc_time", direction="backward")["fund"].to_numpy()
    own = np.log(sp["c"])
    oth = np.log(other_spot["c"].reindex(grid))
    for k in (5, 15, 60):
        f[f"x_r{k}"] = oth - oth.shift(k)
    f["x_rel15"] = (own - own.shift(15)) - f["x_r15"]
    f["x_rel60"] = (own - own.shift(60)) - f["x_r60"]
    return f.reindex(idx)[NEW_FEATURES]


def _logloss(p: np.ndarray, y: np.ndarray) -> np.ndarray:
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return -(y * np.log(p) + (1 - y) * np.log(1 - p))


def run_symbol(symbol: str, root: Path, cfg: dict, n_boot: int = 1000, log=print) -> dict:
    inst = get_instrument(symbol)
    st, cc, ec = cfg["study"], cfg["contracts"], cfg["execution"]
    spot = load(root, symbol, "spot")
    bars = spot_bars(spot)
    bars = bars[(bars.index >= pd.Timestamp(DATA_START, tz="UTC")) & (bars.index < pd.Timestamp(DEV_END, tz="UTC"))]
    pf = compute_features(bars)
    nf = new_features(bars.index, spot, load(root, symbol, "perp"), load(root, symbol, "prem"),
                      load(root, symbol, "fund"), load(root, OTHER[symbol], "spot"))
    lab = make_labels(bars, HORIZON, ENTRY_DELAY, inst.point)
    tie_ind = (lab["dir"] == 0).astype(float).where(lab["dir"].notna())
    q_hat = tie_ind.shift(HORIZON + ENTRY_DELAY).rolling(1440, min_periods=200).mean().to_numpy()  # causal
    # Mismas decisiones para los dos modelos: hace falta que existan TODAS las variables.
    dm = decision_mask(bars.index, HORIZON) & pf.notna().all(axis=1).to_numpy() & nf.notna().all(axis=1).to_numpy()
    rows = np.flatnonzero(dm)
    idx = bars.index[rows]
    Xb = pf.iloc[rows][FEATURES]
    Xn = pd.concat([Xb, nf.iloc[rows]], axis=1)
    L = lab.iloc[rows]
    y = L["dir"].to_numpy()
    label_end = pd.DatetimeIndex(L["label_end"])
    folds = make_folds(DEV_TEST_START, DEV_END, st["step_months"], st["train_months"], st["calib_frac"])
    models = {"referencia_precio": Xb, "precio_mas_bloque_nuevo": Xn}
    p_up = {m: np.full(len(rows), np.nan) for m in models}
    fold_id = np.full(len(rows), -1)
    notes = []
    for fi, fold in enumerate(folds):
        fit, cal, test = fold.masks(idx, label_end)
        valid = ~np.isnan(y) & (y != 0)
        fit_nt, cal_nt = fit & valid, cal & valid
        if test.sum() == 0 or fit_nt.sum() < 1000 or cal_nt.sum() < 300:
            notes.append({"fold": fold.name, "skipped": True})
            continue
        fold_id[test] = fi
        y_fit, y_cal = (y[fit_nt] == 1).astype(int), (y[cal_nt] == 1).astype(int)
        for m, X in models.items():
            _, (pc_raw, pt_raw) = fit_predict_proba("logit", X[fit_nt], y_fit, [X[cal_nt], X[test]],
                                                    seed=ec["seed"], max_rows=st["max_fit_rows"])
            p_up[m][test] = Calibrator().fit(pc_raw, y_cal).transform(pt_raw)
        notes.append({"fold": fold.name, "skipped": False, "fit": int(fit_nt.sum()), "cal": int(cal_nt.sum()),
                      "test": int(test.sum())})
        log(f"[{symbol}] fold {fold.name}: ajuste={fit_nt.sum():,} calib={cal_nt.sum():,} prueba={test.sum():,}")

    sub = fold_id >= 0
    binary = BinaryContract(cc["binary_payout"], cc["binary_tie_rule"])
    local_b = idx[sub].tz_convert("America/Bogota")
    hour_b = local_b.hour.to_numpy()
    day = (local_b.year * 10000 + local_b.month * 100 + local_b.day).to_numpy().astype(np.int64)
    q_sub = np.nan_to_num(q_hat[rows][sub], nan=float(np.nanmean(q_hat)))
    base_exec = ExecParams(latency_median_s=ec["latency_median_s"], latency_sigma=ec["latency_sigma"],
                           max_age_s=max_age_for_horizon(HORIZON, ec["max_age_base_s"]),
                           p_disconnect=ec["p_disconnect"], seed=ec["seed"] + HORIZON)
    labels = {1: L[sub]}  # la entrada con retraso 2 ya está en las etiquetas (como B_lat60)
    out = {"symbol": symbol, "n_decisiones_prueba": int(sub.sum()), "folds": notes, "modelos": {}}
    tie_hint = float(np.nanmean(y[sub] == 0))
    for m in models:
        pu = p_up[m][sub]
        side = np.sign(pu - 0.5)
        p_dir = np.where(side >= 0, pu, 1 - pu)
        want = binary.ev(p_dir, q_sub) >= cc["binary_ev_margin"]
        sim = simulate(side, want, np.zeros(len(side), dtype=bool), labels, binary, base_exec)
        rec = summarize(sim, binary, idx[sub], hour_b, day, fold_id[sub], np.zeros(int(sub.sum()), dtype=int),
                        tie_hint, n_boot)
        out["modelos"][m] = {k: rec.get(k) for k in ("n_trades", "wins", "losses", "ties", "hit", "hit_lo95",
                                                     "hit_hi95", "breakeven", "pvalue", "ev", "ev_lo95", "ev_hi95",
                                                     "total", "max_drawdown", "positive_fold_frac",
                                                     "max_fold_profit_share", "by_fold")}
    # Log-loss en TODAS las decisiones de prueba sin empate (no solo en las operadas), mismo conjunto.
    nt = ~np.isnan(y[sub]) & (y[sub] != 0)
    yy = (y[sub][nt] == 1).astype(float)
    ll_b = _logloss(p_up["referencia_precio"][sub][nt], yy)
    ll_n = _logloss(p_up["precio_mas_bloque_nuevo"][sub][nt], yy)
    diff = block_bootstrap_mean(ll_b - ll_n, day[nt], n_boot=n_boot)  # > 0: el bloque nuevo predice mejor
    out["logloss"] = {"referencia": float(ll_b.mean()), "prueba": float(ll_n.mean()), "mejora": diff["mean"],
                      "mejora_lo95": diff["lo"], "mejora_hi95": diff["hi"], "n": int(nt.sum())}
    acc_b = float(np.mean((p_up["referencia_precio"][sub][nt] >= 0.5) == (yy == 1)))
    acc_n = float(np.mean((p_up["precio_mas_bloque_nuevo"][sub][nt] >= 0.5) == (yy == 1)))
    out["acierto_todas_las_decisiones"] = {"referencia": acc_b, "prueba": acc_n}
    return out


def verdict(results: dict) -> dict:
    """Criterios fijos del pre-registro, para el modelo de prueba de cada hipótesis."""
    hyps = list(results)
    num = lambda v, d: d if v is None or (isinstance(v, float) and np.isnan(v)) else v  # noqa: E731
    p = np.array([num(results[s]["modelos"]["precio_mas_bloque_nuevo"]["pvalue"], 1.0) for s in hyps])
    order, running, holm = np.argsort(p), 0.0, np.empty(len(p))
    for rank, i in enumerate(order):
        running = max(running, (len(p) - rank) * p[i])
        holm[i] = min(running, 1.0)
    out = {}
    for i, s in enumerate(hyps):
        t, b, ll = results[s]["modelos"]["precio_mas_bloque_nuevo"], results[s]["modelos"]["referencia_precio"], \
            results[s]["logloss"]
        c = {"c1_min_300": num(t["n_trades"], 0) >= 300,
             "c2_wilson": num(t["hit_lo95"], 0.0) > num(t["breakeven"], 1.0),
             "c3_holm": bool(holm[i] < 0.05),
             "c4_estable": num(t["positive_fold_frac"], 0.0) >= 0.6 and num(t["max_fold_profit_share"], 9.0) <= 0.5,
             "c5_mejora": num(ll["mejora_lo95"], -1.0) > 0 and num(t["ev"], -9.0) >= num(b["ev"], -9.0)}
        out[s] = {**c, "p_holm": float(holm[i]), "pasa": all(c.values())}
    return out


def run(root: Path = Path("data/raw/estudio3"), out_dir: Path = Path("results/estudio3"), n_boot: int = 1000,
        log=print) -> dict:
    cfg = load_config("config/research.toml")  # solo se lee (no se cambia): mismo walk-forward y ejecución
    res = {s: run_symbol(s, root, cfg, n_boot, log) for s in SYMBOLS}
    v = verdict(res)
    report = {"estudio": "Estudio 3 — fase de desarrollo (pre-registro 9bf123a)", "git_sha": git_sha(),
              "horizonte_min": HORIZON, "retraso_entrada": ENTRY_DELAY, "politica": "B (EV ≥ 0,02)",
              "periodo_prueba": [DEV_TEST_START, DEV_END], "resultados": res, "veredicto": v,
              "pasa_alguna": any(x["pasa"] for x in v.values())}
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "dev.json").write_text(json.dumps(jsonable(report), indent=2, ensure_ascii=False), encoding="utf-8")
    return report
