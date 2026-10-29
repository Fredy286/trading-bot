"""Estudio 34 (pre-registro en docs/01, commit e94f729): réplica de la reversión nocturna en 2024-09 → 2025-08 (24 pares,
precio medio de ticks de HistData, clic a +10 s), con filtro de diferencial normal (H34b) y la variante fuerte (H34c).
"""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

from ..data.histdata_dl import extract_token
from ..data.http import make_session
from .experiment import git_sha, jsonable
from .study22 import BE, _sma, holm
from .study25 import PAIRS, TICK_PAGE
from .study27 import price_at, stats

MONTHS = tuple(p.strftime("%Y-%m") for p in pd.period_range("2024-09", "2025-08", freq="M"))
WARMUP = "2024-08"  # 20 días hábiles previos para la referencia del diferencial (no se evalúa)
START, END = "2024-09-01", "2025-09-01"
L, SPREAD_MULT, SPREAD_DAYS = 10, 1.5, 20
WORK = Path("data/raw/histdata_ticks_s34")
HYPS = {"H34a": (20, 2.0, 3, False), "H34b": (20, 2.0, 3, True), "H34c": (30, 2.5, 5, False)}


def month_data(pair: str, ym: str, work: Path = WORK) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Por segundo: último precio medio y último diferencial; por minuto: velas del precio medio y mediana del diferencial."""
    f_s, f_m = Path(work) / pair / f"{ym}_seg.parquet", Path(work) / pair / f"{ym}_min.parquet"
    if not f_s.exists():
        y, m = ym.split("-")
        s = make_session()
        page = TICK_PAGE.format(pair=pair.lower(), y=y, m=int(m))
        tk = extract_token(s.get(page, timeout=60).text)
        data = {"tk": tk, "date": y, "datemonth": f"{y}{m}", "platform": "ASCII", "timeframe": "T", "fxpair": pair}
        blob = s.post("https://www.histdata.com/get.php", data=data, timeout=600,
                      headers={"Referer": page, "Origin": "https://www.histdata.com"}).content
        with zipfile.ZipFile(io.BytesIO(blob)) as zf:
            name = next(n for n in zf.namelist() if n.lower().endswith(".csv"))
            raw = pd.read_csv(io.BytesIO(zf.read(name)), header=None, names=["t", "bid", "ask", "v"])
        t = pd.DatetimeIndex(pd.to_datetime(raw["t"], format="%Y%m%d %H%M%S%f") + pd.Timedelta(hours=5)).tz_localize("UTC")
        mid = pd.Series(((raw["bid"] + raw["ask"]) / 2).to_numpy(), index=t)
        spread = pd.Series((raw["ask"] - raw["bid"]).to_numpy(), index=t)
        g = mid.resample("min")
        bars = pd.DataFrame({"o": g.first(), "h": g.max(), "l": g.min(), "c": g.last(),
                             "spread_med": spread.resample("min").median()})
        sec = pd.DataFrame({"mid": mid.groupby(t.floor("s")).last(), "spread": spread.groupby(t.floor("s")).last()})
        f_s.parent.mkdir(parents=True, exist_ok=True)
        sec.to_parquet(f_s)
        bars.to_parquet(f_m)
        print(f"  {pair} {ym}: {len(raw):,} ticks", flush=True)
    return pd.read_parquet(f_s), pd.read_parquet(f_m)


def band(bars: pd.DataFrame, n: int, k: float) -> pd.Series:
    """Dirección de la reversión en la vela objetivo t = s + 1 min, ventana 21–24 UTC (hora de t)."""
    real = bars.dropna(subset=["c"])
    c = real["c"].to_numpy()
    mid, sd = _sma(c, n), pd.Series(c).rolling(n).std(ddof=0).to_numpy()
    bb = np.where(c > mid + k * sd, -1.0, np.where(c < mid - k * sd, 1.0, np.nan))
    s = pd.Series(bb, index=real.index + pd.Timedelta(minutes=1)).dropna()
    return s[s.index.hour >= 21]


def one_at_a_time(t: pd.DatetimeIndex, minutes: int) -> np.ndarray:
    keep, busy = np.zeros(len(t), bool), None
    for i, x in enumerate(t):
        if busy is None or x >= busy:
            keep[i], busy = True, x + pd.Timedelta(minutes=minutes)
    return keep


def spread_reference(bars: pd.DataFrame) -> pd.Series:
    """Por día: mediana de los 20 días hábiles ANTERIORES de la mediana nocturna (21–24 UTC) del diferencial por minuto."""
    night = bars["spread_med"][bars.index.hour >= 21].dropna()
    daily = night.groupby(night.index.floor("D")).median()
    return daily.rolling(SPREAD_DAYS, min_periods=SPREAD_DAYS).median().shift(1)


def pair_rows(pair: str, log=print) -> pd.DataFrame:
    parts = [month_data(pair, ym) for ym in (WARMUP,) + MONTHS]
    sec = pd.concat([p[0] for p in parts]).sort_index()
    sec = sec[~sec.index.duplicated(keep="last")]
    bars = pd.concat([p[1] for p in parts]).sort_index()
    bars = bars[~bars.index.duplicated(keep="last")]
    bars = bars.reindex(pd.date_range(bars.index[0], bars.index[-1], freq="min", tz="UTC"))
    ref = spread_reference(bars)
    out = []
    for h, (n, k, dur, filt) in HYPS.items():
        s = band(bars, n, k)
        s = s[(s.index >= pd.Timestamp(START, tz="UTC")) & (s.index < pd.Timestamp(END, tz="UTC"))]
        sp = price_at(sec["spread"], s.index)  # diferencial del último tick antes del cierre de s (= t)
        r = ref.reindex(s.index.floor("D")).to_numpy()
        rel = sp / r
        if filt:
            keep = ~np.isnan(rel) & (rel <= SPREAD_MULT)
            s, rel = s[keep], rel[keep]
        sel = one_at_a_time(s.index, dur)
        s, rel = s[sel], rel[sel]
        e = price_at(sec["mid"], s.index + pd.Timedelta(seconds=L))
        x = price_at(sec["mid"], s.index + pd.Timedelta(seconds=L + 60 * dur))
        d = x - e
        res = np.where(np.isnan(d), np.nan, np.sign(np.where(np.abs(d) < 1e-9, 0.0, d)))
        out.append(pd.DataFrame({"h": h, "dir": s.to_numpy(), "res": res, "par": pair, "dif_rel": rel}, index=s.index))
    log(f"  {pair}: listo")
    return pd.concat(out)


def run(out_dir: Path = Path("results/estudio34"), log=print) -> dict:
    allr = pd.concat([pair_rows(p, log) for p in PAIRS]).sort_index()
    res = {}
    for h in HYPS:
        g = allr[allr["h"] == h]
        res[h] = stats(g["dir"].to_numpy(), g["res"].to_numpy(), g.index)
    adj = holm([res[h]["p"] for h in HYPS])
    for (h, x), pa in zip(res.items(), adj):
        crit = {"min_n": x["operaciones"] >= (500 if h == "H34c" else 1000), "holm": pa < 0.05,
                "wilson": x["lo95"] > BE, "meses_9de12": x["meses_ev_positivo"] >= 9,
                "simetria": abs(x["call"] - x["put"]) < 0.05}
        x.update({"p_holm": pa, "criterios": crit, "pasa": all(crit.values())})
        log(f"{h}: pasa={x['pasa']} | {x['operaciones']} ops, acierto {x['acierto']:.4f} [{x['lo95']:.4f}] "
            f"CALL {x['call']:.3f} PUT {x['put']:.3f} meses+ {x['meses_ev_positivo']} | {crit}")
    a = allr[allr["h"] == "H34a"].copy()
    info = {}
    ok = a["dif_rel"].notna()
    if ok.any():
        dec = pd.qcut(a.loc[ok, "dif_rel"], 10, labels=False, duplicates="drop")
        info["por_decil_diferencial"] = {
            int(q): {"dif_rel_max": float(g["dif_rel"].max()),
                     **{k: v for k, v in stats(g["dir"].to_numpy(), g["res"].to_numpy(), g.index).items()
                        if k in ("operaciones", "acierto")}}
            for q, g in a.loc[ok].groupby(dec)}
    info["hora_22_H34a"] = stats(a[a.index.hour == 22]["dir"].to_numpy(), a[a.index.hour == 22]["res"].to_numpy(),
                                 a[a.index.hour == 22].index)["acierto"]
    info["por_par_H34a"] = {p: stats(g["dir"].to_numpy(), g["res"].to_numpy(), g.index)["acierto"]
                            for p, g in a.groupby("par")}
    rep = {"estudio": "Estudio 34 — réplica 2024-09 → 2025-08 y filtro de diferencial (pre-registro e94f729)",
           "git_sha": git_sha(), "periodo": [START, END], "hipotesis": res, "informativo": info}
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "resultado.json").write_text(json.dumps(jsonable(rep), indent=2, ensure_ascii=False), encoding="utf-8")
    return rep
