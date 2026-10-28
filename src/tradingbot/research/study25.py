"""Estudio 25 (pre-registro en docs/01, commit a3960ce): reversión nocturna de Bollinger (regla del Estudio 22) en 24
pares que el Estudio 22 no usó, 2025-09-01 → 2026-10-23, todos juntos.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from .experiment import git_sha, jsonable
from .metrics import binom_pvalue_greater, wilson
from .study22 import BE, PAYOUT, color, indicator_rules, lag

PAIRS = ("AUDCAD", "AUDCHF", "AUDJPY", "AUDNZD", "AUDUSD", "CADCHF", "CADJPY", "CHFJPY", "EURAUD", "EURCAD", "EURCHF",
         "EURGBP", "EURJPY", "EURNZD", "GBPAUD", "GBPCAD", "GBPCHF", "GBPJPY", "GBPNZD", "NZDCAD", "NZDCHF", "NZDJPY",
         "NZDUSD", "USDCAD")
START, END = "2025-09-01", "2026-10-24"
RULE = "Bollinger_rev_3min_21a24UTC"


def load_pair(pair: str, root: Path = Path("data/raw/histdata_pares")) -> pd.DataFrame:
    files = [f for f in sorted((Path(root) / pair).glob("*.parquet")) if f.stem >= "2025"]
    df = pd.concat([pd.read_parquet(f) for f in files])[["bid_o", "bid_h", "bid_l", "bid_c"]]
    df.columns = ["o", "h", "l", "c"]
    df = df[~df.index.duplicated(keep="last")].sort_index()
    return df.reindex(pd.date_range(df.index[0], df.index[-1], freq="min", tz="UTC"))


def trades(bars: pd.DataFrame) -> pd.DataFrame:
    """Operaciones de la regla (misma lógica que study22.run_symbol): dirección, resultado a 3 min, una a la vez."""
    d = indicator_rules(bars)[RULE]
    col = color(bars["o"].to_numpy(), bars["c"].to_numpy())
    res = color(bars["o"].to_numpy(), lag(bars["c"].to_numpy(), -2))
    res = np.where(np.isnan(lag(col, -1)) | np.isnan(lag(col, -2)), np.nan, res)
    rows, busy = [], -1
    for i in np.flatnonzero(~np.isnan(d) & ~np.isnan(res)):
        if i > busy:
            rows.append((bars.index[i], d[i], res[i]))
            busy = i + 2
    t = pd.DataFrame(rows, columns=["t", "dir", "res"]).set_index("t")
    return t[(t.index >= pd.Timestamp(START, tz="UTC")) & (t.index < pd.Timestamp(END, tz="UTC"))]


def stats(t: pd.DataFrame) -> dict:
    r = (t["dir"] * t["res"]).to_numpy()
    n, w, ties = int((r != 0).sum()), int((r > 0).sum()), int((r == 0).sum())
    lo, _ = wilson(w, n) if n else (float("nan"), 0)
    pnl = np.where(r == 0, 0.0, np.where(r > 0, PAYOUT, -1.0))
    return {"operaciones": int(len(t)), "sin_empate": n, "acierto": w / n if n else None, "lo95": float(lo),
            "acierto_empate_pierde": w / (n + ties) if n + ties else None, "ev": float(pnl.mean()) if len(t) else None,
            "p": binom_pvalue_greater(w, n, BE) if n else 1.0, "p_azar": binom_pvalue_greater(w, n, 0.5) if n else 1.0}


def run(out_dir: Path = Path("results/estudio25"), log=print) -> dict:
    parts = []
    for p in PAIRS:
        t = trades(load_pair(p)).assign(par=p)
        parts.append(t)
        log(f"  {p}: {len(t)} operaciones")
    allt = pd.concat(parts).sort_index()
    main = stats(allt)
    r = allt["dir"] * allt["res"]
    pnl = np.where(r == 0, 0.0, np.where(r > 0, PAYOUT, -1.0))
    mens = pd.Series(pnl, index=allt.index).groupby(allt.index.strftime("%Y-%m")).mean()
    main["meses_ev_positivo"] = float((mens > 0).mean())
    crit = {"min_1000": main["operaciones"] >= 1000, "p": main["p"] < 0.05, "wilson": main["lo95"] > BE,
            "meses_60": main["meses_ev_positivo"] >= 0.6}
    rep = {"estudio": "Estudio 25 — reversión nocturna en 24 pares nuevos (pre-registro a3960ce)", "git_sha": git_sha(),
           "periodo": [START, END], **main, "mensual": mens.round(4).to_dict(), "criterios": crit,
           "pasa": all(crit.values()),
           "por_par": {p: stats(g) for p, g in allt.groupby("par")},
           "por_hora": {int(h): stats(g)["acierto"] for h, g in allt.groupby(allt.index.hour)}}
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "resultado.json").write_text(json.dumps(jsonable(rep), indent=2, ensure_ascii=False), encoding="utf-8")
    log(f"H25: pasa={rep['pasa']} | {crit} | {main}")
    return rep


# ----------------------------------------------------------------------- verificación con precio medio (ticks)
VERIF_PAIRS = ("EURGBP", "EURCHF", "EURAUD", "GBPCAD", "CHFJPY", "EURJPY")
VERIF_MONTHS = ("2026-04", "2026-05", "2026-06", "2026-07", "2026-08", "2026-09")
TICK_PAGE = "https://www.histdata.com/download-free-forex-historical-data/?/ascii/tick-data-quotes/{pair}/{y}/{m}"


def tick_bars(pair: str, ym: str, work: Path = Path("data/raw/histdata_ticks")) -> pd.DataFrame:
    """Velas de 1 min de bid y de precio medio a partir de los ticks de HistData (hora EST fija = UTC−5)."""
    import io
    import zipfile

    from ..data.histdata_dl import extract_token
    from ..data.http import make_session

    f = Path(work) / pair / f"{ym}.parquet"
    if not f.exists():
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
        t = pd.to_datetime(raw["t"], format="%Y%m%d %H%M%S%f") + pd.Timedelta(hours=5)
        ticks = pd.DataFrame({"bid": raw["bid"].to_numpy(), "mid": ((raw["bid"] + raw["ask"]) / 2).to_numpy()},
                             index=pd.DatetimeIndex(t).tz_localize("UTC"))
        out = {}
        for k in ("bid", "mid"):
            g = ticks[k].resample("min")
            out.update({f"{k}_o": g.first(), f"{k}_h": g.max(), f"{k}_l": g.min(), f"{k}_c": g.last()})
        f.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(out).to_parquet(f)
    return pd.read_parquet(f)


def verify_mid(out_dir: Path = Path("results/estudio25"), log=print) -> dict:
    rep = {"estudio": "Estudio 25 — verificación con precio medio de ticks", "git_sha": git_sha(), "precios": {}}
    for k in ("mid", "bid"):
        parts = []
        for p in VERIF_PAIRS:
            df = pd.concat([tick_bars(p, ym) for ym in VERIF_MONTHS]).sort_index()
            bars = df[[f"{k}_o", f"{k}_h", f"{k}_l", f"{k}_c"]].set_axis(["o", "h", "l", "c"], axis=1)
            bars = bars.reindex(pd.date_range(bars.index[0], bars.index[-1], freq="min", tz="UTC"))
            t = trades(bars)
            parts.append(t[(t.index >= pd.Timestamp("2026-04-01", tz="UTC"))].assign(par=p))
            log(f"  {k} {p}: {len(parts[-1])} operaciones")
        t = pd.concat(parts)
        x = stats(t)
        x["call"] = stats(t[t["dir"] > 0])["acierto"]
        x["put"] = stats(t[t["dir"] < 0])["acierto"]
        rep["precios"][k] = x
        log(f"{k}: {x}")
    m = rep["precios"]["mid"]
    rep["criterios"] = {"acierto_wilson": m["lo95"] > BE, "simetria_5pts": abs(m["call"] - m["put"]) < 0.05}
    rep["pasa"] = all(rep["criterios"].values())
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    (Path(out_dir) / "verificacion_precio_medio.json").write_text(json.dumps(jsonable(rep), indent=2,
                                                                              ensure_ascii=False), encoding="utf-8")
    return rep
