"""Estudio 65 (pre-registro 2fc1979, docs/01): el gran bot ampliado con cuatro opiniones más (ETH, SOL, XRP y DOGE a
1 min, receta H16b del Estudio 26), comparado con el gran bot de 6 opiniones del Estudio 63 en las mismas filas.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import study63 as s63
from .experiment import git_sha, jsonable

E26 = {f"e26_{c[:-4].lower()}": Path(f"data/processed/estudio26/{c}/predicciones.parquet")
       for c in ("ETHUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT")}
OPINIONES10 = (*s63.OPINIONES, *E26)
N_BOOT = 10_000
SEMILLA = 65


def tabla(moneda: str, p54: pd.DataFrame, otras: dict[str, pd.Series]) -> pd.DataFrame:
    df = s63.tabla(moneda, p54, {k: v for k, v in otras.items() if k in s63.FUENTES})
    for k in E26:
        df[k] = otras[k].reindex(df.index)
    return df.dropna(subset=list(OPINIONES10))


def walk_forward(df: pd.DataFrame, opiniones: tuple[str, ...]) -> tuple[pd.Series, dict]:
    mes = np.asarray(df.index.tz_convert(None).to_period("M").astype(str))
    X, y = s63.logit(df[list(opiniones)].to_numpy()), (df["y"].to_numpy() > 0).astype(float)
    out, coefs = pd.Series(np.nan, index=df.index), {}
    for m in s63.PRUEBA:
        ini = pd.Timestamp(m + "-01", tz="UTC")
        train = np.asarray(df.index < ini - s63.PURGA)
        test = mes == m
        if train.sum() < 1000 or not test.any():
            continue
        b = s63.logistica(X[train], y[train])
        out[test] = s63.predecir(b, X[test])
        coefs[m] = dict(zip(("constante", *opiniones), (float(x) for x in b)))
    return out, coefs


def run(out_dir: Path = Path("results/estudio65"), n_boot: int = N_BOOT, log=print) -> dict:
    p54 = pd.read_parquet(s63.P54)
    otras = {k: pd.read_parquet(f)["p"] for k, f in {**s63.FUENTES, **E26}.items()}
    partes, coefs = [], {}
    for m in s63.MONEDAS:
        df = tabla(m, p54, otras)
        p6, _ = walk_forward(df, s63.OPINIONES)
        p10, c10 = walk_forward(df, OPINIONES10)
        partes.append(df.assign(seis=p6, diez=p10).dropna(subset=["seis", "diez"]))
        coefs[m] = c10
    res = pd.concat(partes).sort_index()
    y = res["y"].to_numpy()
    t6, g6 = s63.politica(res["seis"].to_numpy(), y)
    t10, g10 = s63.politica(res["diez"].to_numpy(), y)
    tb, gb = s63.politica(res["propia"].to_numpy(), y)
    iso = res.index.isocalendar()
    semanas = (iso["year"].astype(int) * 100 + iso["week"].astype(int)).to_numpy()
    d = s63._boot_semanas(g10 - g6, semanas, n_boot, SEMILLA)
    lim = float(np.quantile(d, 0.05))
    crit = {"limite_5_mayor_0": lim > 0, "min_300": int(t10.sum()) >= 300}
    ll6, ll10 = s63._logloss(res["seis"].to_numpy(), y), s63._logloss(res["diez"].to_numpy(), y)
    rep = {"estudio": "Estudio 65 — gran bot ampliado a 10 opiniones (pre-registro 2fc1979)", "filas": int(len(res)),
           "principal": {"delta_ganancia": float(g10.sum() - g6.sum()), "limite_inferior_5": lim,
                         "p_bootstrap": float((d <= 0).mean()), "criterios": crit},
           "pasa": all(crit.values()),
           "seis": s63._resumen(t6, g6, res.index), "diez": s63._resumen(t10, g10, res.index),
           "base": s63._resumen(tb, gb, res.index),
           "logloss": {"seis": float(ll6.mean()), "diez": float(ll10.mean()), "delta": float((ll10 - ll6).mean())},
           "por_moneda": {}, "coeficientes": coefs, "git_sha": git_sha()}
    for m in s63.MONEDAS:
        s = (res["moneda"] == m).to_numpy()
        rep["por_moneda"][m] = {"seis": s63._resumen(t6 & s, np.where(s, g6, 0.0), res.index[s]),
                                "diez": s63._resumen(t10 & s, np.where(s, g10, 0.0), res.index[s]),
                                "delta_ganancia": float(g10[s].sum() - g6[s].sum())}
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "resultado.json").write_text(json.dumps(jsonable(rep), indent=2, ensure_ascii=False) + "\n",
                                            encoding="utf-8")
    log(f"H65: pasa={rep['pasa']} | ΔG={rep['principal']['delta_ganancia']:+.2f} (lím. 5 % {lim:+.2f}) | "
        f"6 opiniones {rep['seis']} | 10 opiniones {rep['diez']}")
    return rep
