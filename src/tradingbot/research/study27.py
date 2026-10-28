"""Estudio 27 (pre-registro en docs/01, commit f125c8d): reversión nocturna de Bollinger en divisas con precio medio de
ticks, clic humano a +L s y vencimiento de 3 min desde la entrada, en los 24 pares del Estudio 25 (2026-04 → 2026-09).
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
from .metrics import binom_pvalue_greater, wilson
from .study22 import BE, PAYOUT, indicator_rules
from .study25 import PAIRS, RULE, TICK_PAGE

MONTHS = ("2026-04", "2026-05", "2026-06", "2026-07", "2026-08", "2026-09")
LATS = {"H27a": 5, "H27b": 10}
INFO_LATS = (0, 2, 20, 30)
MAX_AGE_S = 60  # un precio solo vale si su último tick tiene ≤ 60 s (nota de implementación)
WORK = Path("data/raw/histdata_ticks_seg")


def seconds(pair: str, ym: str, work: Path = WORK) -> pd.DataFrame:
    """Último precio medio de cada segundo con ticks, y velas de 1 min del precio medio (hora EST fija = UTC−5)."""
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
        g = mid.resample("min")
        bars = pd.DataFrame({"o": g.first(), "h": g.max(), "l": g.min(), "c": g.last()})
        sec = mid.groupby(t.floor("s")).last()
        f_s.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame({"mid": sec}).to_parquet(f_s)
        bars.to_parquet(f_m)
        print(f"  {pair} {ym}: {len(raw):,} ticks", flush=True)
    return pd.read_parquet(f_s), pd.read_parquet(f_m)


def price_at(sec: pd.Series, when: pd.DatetimeIndex) -> np.ndarray:
    """Precio medio del último tick ANTES de `when` (segundo que abre como mucho en when − 1 s), si tiene ≤ 60 s."""
    ts = sec.index.as_unit("ns").asi8
    q = (when - pd.Timedelta(seconds=1)).as_unit("ns").asi8
    j = np.searchsorted(ts, q, side="right") - 1
    ok = j >= 0
    jj = np.clip(j, 0, None)
    age = (q - ts[jj]) / 1e9
    return np.where(ok & (age <= MAX_AGE_S), sec.to_numpy()[jj], np.nan)


def pair_trades(pair: str, log=print) -> pd.DataFrame:
    parts = [seconds(pair, ym) for ym in MONTHS]
    sec = pd.concat([p[0] for p in parts])["mid"].sort_index()
    sec = sec[~sec.index.duplicated(keep="last")]
    bars = pd.concat([p[1] for p in parts]).sort_index()
    bars = bars[~bars.index.duplicated(keep="last")]
    bars = bars.reindex(pd.date_range(bars.index[0], bars.index[-1], freq="min", tz="UTC"))
    d = indicator_rules(bars)[RULE]  # dirección en la vela objetivo t = s + 1 min (señal al cierre de s)
    idx = np.flatnonzero(~np.isnan(d))
    keep, busy = [], None
    for i in idx:  # una operación a la vez (la anterior vence 3 min después de su entrada)
        if busy is None or bars.index[i] >= busy:
            keep.append(i)
            busy = bars.index[i] + pd.Timedelta(minutes=3)
    t = bars.index[keep]
    out = pd.DataFrame({"dir": d[keep], "par": pair}, index=t)
    for L in sorted(set(LATS.values()) | set(INFO_LATS)):
        e = price_at(sec, t + pd.Timedelta(seconds=L))
        x = price_at(sec, t + pd.Timedelta(seconds=L + 180))
        diff = x - e
        out[f"res_L{L}"] = np.where(np.isnan(diff), np.nan, np.sign(np.where(np.abs(diff) < 1e-9, 0.0, diff)))
    log(f"  {pair}: {len(out)} señales")
    return out


def stats(dirs: np.ndarray, res: np.ndarray, times: pd.DatetimeIndex, payout: float = PAYOUT) -> dict:
    m = ~np.isnan(res)
    r = dirs[m] * res[m]
    n, w, ties = int((r != 0).sum()), int((r > 0).sum()), int((r == 0).sum())
    lo, _ = wilson(w, n) if n else (float("nan"), 0)
    pnl = np.where(r == 0, 0.0, np.where(r > 0, payout, -1.0))
    mens = pd.Series(pnl, index=times[m]).groupby(times[m].strftime("%Y-%m")).mean()
    call = (r[dirs[m] > 0] > 0).sum() / max((r[dirs[m] > 0] != 0).sum(), 1)
    put = (r[dirs[m] < 0] > 0).sum() / max((r[dirs[m] < 0] != 0).sum(), 1)
    return {"operaciones": int(m.sum()), "sin_empate": n, "acierto": w / n if n else None, "lo95": float(lo),
            "acierto_empate_pierde": w / (n + ties) if n + ties else None, "ev": float(pnl.mean()) if len(pnl) else None,
            "p": binom_pvalue_greater(w, n, BE) if n else 1.0, "call": float(call), "put": float(put),
            "meses_ev_positivo": int((mens > 0).sum()), "mensual": mens.round(4).to_dict()}


def run(out_dir: Path = Path("results/estudio27"), log=print) -> dict:
    allt = pd.concat([pair_trades(p, log) for p in PAIRS]).sort_index()
    allt = allt[allt.index >= pd.Timestamp("2026-04-01", tz="UTC")]
    rep = {"estudio": "Estudio 27 — reversión nocturna con clic humano (pre-registro f125c8d)", "git_sha": git_sha(),
           "meses": MONTHS, "hipotesis": {}, "informativo": {}}
    dirs, times = allt["dir"].to_numpy(), allt.index
    for h, L in LATS.items():
        x = stats(dirs, allt[f"res_L{L}"].to_numpy(), times)
        crit = {"min_1000": x["operaciones"] >= 1000, "p": x["p"] < 0.025, "wilson": x["lo95"] > BE,
                "meses_5de6": x["meses_ev_positivo"] >= 5, "simetria": abs(x["call"] - x["put"]) < 0.05}
        rep["hipotesis"][h] = {"latencia_s": L, **x, "criterios": crit, "pasa": all(crit.values())}
        log(f"{h} (L={L}s): pasa={all(crit.values())} | {x['operaciones']} ops, acierto {x['acierto']:.4f} "
            f"[{x['lo95']:.4f}] CALL {x['call']:.3f} PUT {x['put']:.3f} | {crit}")
    for L in INFO_LATS:
        x = stats(dirs, allt[f"res_L{L}"].to_numpy(), times)
        x.pop("mensual")
        rep["informativo"][f"L={L}s"] = x
        log(f"  informativo L={L}s: acierto {x['acierto']:.4f}")
    r10 = allt["res_L10"].to_numpy()
    rep["informativo"]["por_par_L10"] = {p: stats(g["dir"].to_numpy(), g["res_L10"].to_numpy(), g.index)["acierto"]
                                        for p, g in allt.groupby("par")}
    rep["informativo"]["por_hora_L10"] = {int(hh): stats(g["dir"].to_numpy(), g["res_L10"].to_numpy(), g.index)["acierto"]
                                         for hh, g in allt.groupby(allt.index.hour)}
    rep["informativo"]["equilibrios"] = {f"pago {int(b * 100)} %": 1 / (1 + b) for b in (0.70, 0.75, 0.80, 0.85)}
    rep["informativo"]["senales_por_dia_habil"] = float(np.isfinite(r10).sum() / max(len(set(times.strftime("%Y-%m-%d"))), 1))
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "resultado.json").write_text(json.dumps(jsonable(rep), indent=2, ensure_ascii=False), encoding="utf-8")
    return rep
