"""Estudio 28 (pre-registro en docs/01, commit cac723d): reversión nocturna (regla de H27b) en invierno de Nueva York,
2025-11 → 2026-03, con ventana fija 21–24 UTC (H28a) o anclada a las 17:00–19:59 de Nueva York (H28b).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from .experiment import git_sha, jsonable
from .study22 import BE, _sma
from .study25 import PAIRS
from .study27 import price_at, seconds, stats

MONTHS = ("2025-11", "2025-12", "2026-01", "2026-02", "2026-03")
SUMMER = ("2026-04", "2026-05", "2026-06", "2026-07", "2026-08", "2026-09")
L = 10


def band_signal(bars: pd.DataFrame) -> pd.Series:
    """Bollinger (20, 2) con reversión al cierre de la vela s, puesta en la vela objetivo t = s + 1 min (sin filtro horario)."""
    real = bars.dropna()
    c = real["c"].to_numpy()
    mid, sd = _sma(c, 20), pd.Series(c).rolling(20).std(ddof=0).to_numpy()
    bb = np.where(c > mid + 2 * sd, -1.0, np.where(c < mid - 2 * sd, 1.0, np.nan))
    return pd.Series(bb, index=real.index + pd.Timedelta(minutes=1)).dropna()


def windows(t: pd.DatetimeIndex) -> dict[str, np.ndarray]:
    ny = t.tz_convert("America/New_York")
    return {"H28a": t.hour.to_numpy() >= 21, "H28b": (ny.hour.to_numpy() >= 17) & (ny.hour.to_numpy() < 20)}


def one_at_a_time(t: pd.DatetimeIndex) -> np.ndarray:
    keep, busy = np.zeros(len(t), bool), None
    for i, x in enumerate(t):
        if busy is None or x >= busy:
            keep[i], busy = True, x + pd.Timedelta(minutes=3)
    return keep


def pair_rows(pair: str, months, log=print) -> pd.DataFrame:
    parts = [seconds(pair, ym) for ym in months]
    sec = pd.concat([p[0] for p in parts])["mid"].sort_index()
    sec = sec[~sec.index.duplicated(keep="last")]
    bars = pd.concat([p[1] for p in parts]).sort_index()
    bars = bars[~bars.index.duplicated(keep="last")]
    bars = bars.reindex(pd.date_range(bars.index[0], bars.index[-1], freq="min", tz="UTC"))
    sig = band_signal(bars)
    sig = sig[sig.index >= pd.Timestamp(months[0] + "-01", tz="UTC")]
    rng = (bars["h"] - bars["l"]).resample("D").sum()  # volatilidad del día (suma de rangos de 1 min)
    out = []
    for h, w in windows(sig.index).items():
        s = sig[w]
        s = s[one_at_a_time(s.index)]
        e = price_at(sec, s.index + pd.Timedelta(seconds=L))
        x = price_at(sec, s.index + pd.Timedelta(seconds=L + 180))
        d = x - e
        res = np.where(np.isnan(d), np.nan, np.sign(np.where(np.abs(d) < 1e-9, 0.0, d)))
        prev_vol = rng.shift(1).reindex(s.index.floor("D")).to_numpy() / np.nanmedian(rng)
        out.append(pd.DataFrame({"h": h, "dir": s.to_numpy(), "res": res, "par": pair, "vol_prev": prev_vol},
                                index=s.index))
    log(f"  {pair}: {sum(len(o) for o in out)} señales")
    return pd.concat(out)


def run(out_dir: Path = Path("results/estudio28"), log=print) -> dict:
    allr = pd.concat([pair_rows(p, MONTHS, log) for p in PAIRS]).sort_index()
    rep = {"estudio": "Estudio 28 — reversión nocturna en invierno (pre-registro cac723d)", "git_sha": git_sha(),
           "meses": MONTHS, "hipotesis": {}, "informativo": {}}
    for h in ("H28a", "H28b"):
        g = allr[allr["h"] == h]
        x = stats(g["dir"].to_numpy(), g["res"].to_numpy(), g.index)
        crit = {"min_1000": x["operaciones"] >= 1000, "p": x["p"] < 0.025, "wilson": x["lo95"] > BE,
                "meses_4de5": x["meses_ev_positivo"] >= 4, "simetria": abs(x["call"] - x["put"]) < 0.05}
        rep["hipotesis"][h] = {**x, "criterios": crit, "pasa": all(crit.values())}
        log(f"{h}: pasa={all(crit.values())} | {x['operaciones']} ops, acierto {x['acierto']:.4f} [{x['lo95']:.4f}] "
            f"CALL {x['call']:.3f} PUT {x['put']:.3f} | {crit}")
    a, b = rep["hipotesis"]["H28a"], rep["hipotesis"]["H28b"]
    rep["ventana_en_vivo"] = "nueva_york" if b["pasa"] and b["acierto"] >= a["acierto"] else "utc"
    # Informativo: horas desde el cierre de Nueva York, juntando invierno (este estudio) y verano (Estudio 27)
    summer = pd.concat([pair_rows(p, SUMMER, lambda *_: None) for p in PAIRS])
    both = pd.concat([allr.assign(estacion="invierno"), summer.assign(estacion="verano")])
    ny = both.index.tz_convert("America/New_York")
    both["h_ny"] = ny.hour
    rep["informativo"]["por_hora_nueva_york"] = {
        f"{est} {hh}:00 NY": stats(g["dir"].to_numpy(), g["res"].to_numpy(), g.index)["acierto"]
        for (est, hh), g in both[both["h"] == "H28b"].groupby(["estacion", "h_ny"])}
    hb = allr[allr["h"] == "H28b"]
    rep["informativo"]["volatilidad_previa"] = {
        k: stats(g["dir"].to_numpy(), g["res"].to_numpy(), g.index)["acierto"]
        for k, g in hb.groupby(np.where(hb["vol_prev"] > 1, "alta", "baja"))}
    rep["informativo"]["por_par_H28b"] = {p: stats(g["dir"].to_numpy(), g["res"].to_numpy(), g.index)["acierto"]
                                          for p, g in hb.groupby("par")}
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "resultado.json").write_text(json.dumps(jsonable(rep), indent=2, ensure_ascii=False), encoding="utf-8")
    log(f"Ventana para el modo en vivo: {rep['ventana_en_vivo']} | {rep['informativo']}")
    return rep
