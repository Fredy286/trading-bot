"""Estudio 67 (pre-registro 0e10605, docs/01): el gran bot de los contratos de 15 min de OKX (ETH y BTC).

Ocho opiniones en cada minuto de decisión de 15 min (todas fuera de muestra, hasta el segundo 49): la propia y la de la
otra moneda a 15 min y a 5 min (Estudio 54), p20, p42, p51 y p53. Etiqueta del Estudio 54 a 15 min; regla de OKX.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import apilado
from . import study63 as s63
from .experiment import git_sha, jsonable

OPINIONES = ("propia15", "otra15", "propia5", "otra5", "p20", "p42", "p51", "p53")
N_BOOT = 10_000
SEMILLA = 67


def tabla(moneda: str, p54: pd.DataFrame, otras: dict[str, pd.Series]) -> pd.DataFrame:
    otra = [m for m in s63.MONEDAS if m != moneda][0]

    def serie(sym, dur):
        x = p54[(p54["simbolo"] == sym) & (p54["dur"] == dur)]
        return x

    mia15 = serie(moneda, 15)
    df = pd.DataFrame({"propia15": mia15["p"], "y": mia15["y"]}, index=mia15.index)
    df["otra15"] = serie(otra, 15)["p"].reindex(df.index)
    df["propia5"] = serie(moneda, 5)["p"].reindex(df.index)
    df["otra5"] = serie(otra, 5)["p"].reindex(df.index)
    for k, s in otras.items():
        df[k] = s.reindex(df.index)
    df = df[(df.index >= s63.INICIO) & (df.index < s63.FIN)].dropna(subset=[*OPINIONES, "y"])
    df["moneda"] = moneda
    return df


def run(out_dir: Path = Path("results/estudio67"), n_boot: int = N_BOOT, log=print, p54_path: Path | None = None,
        fuentes: dict | None = None) -> dict:
    p54 = pd.read_parquet(p54_path or s63.P54)
    otras = {k: pd.read_parquet(f)["p"] for k, f in (fuentes or s63.FUENTES).items()}
    partes, coefs = [], {}
    for m in s63.MONEDAS:
        df = tabla(m, p54, otras)
        gran, c = apilado.walk_forward(df, OPINIONES)
        partes.append(df.assign(gran=gran).dropna(subset=["gran"]))
        coefs[m] = c
    res = pd.concat(partes).sort_index()
    y = res["y"].to_numpy()
    tg, gg = s63.politica(res["gran"].to_numpy(), y)
    tb, gb = s63.politica(res["propia15"].to_numpy(), y)
    comp = apilado.comparar(gg, gb, res.index, n_boot, SEMILLA)
    crit = {"limite_5_mayor_0": comp["limite_inferior_5"] > 0, "min_300": int(tg.sum()) >= 300}
    usr = (res.index.hour >= 2) & (res.index.hour < 6)
    rep = {"estudio": "Estudio 67 — gran bot de OKX 15 min (pre-registro 0e10605)", "filas": int(len(res)),
           "principal": {**comp, "criterios": crit}, "pasa": all(crit.values()),
           "base": s63._resumen(tb, gb, res.index), "gran_bot": s63._resumen(tg, gg, res.index),
           "logloss": {"base": float(s63._logloss(res["propia15"].to_numpy(), y).mean()),
                       "gran_bot": float(s63._logloss(res["gran"].to_numpy(), y).mean())},
           "por_moneda": {m: {"base": s63._resumen(tb & (res["moneda"] == m).to_numpy(),
                                                   np.where(res["moneda"] == m, gb, 0.0), res.index),
                              "gran_bot": s63._resumen(tg & (res["moneda"] == m).to_numpy(),
                                                       np.where(res["moneda"] == m, gg, 0.0), res.index)}
                          for m in s63.MONEDAS},
           "horario_usuario": {"base": s63._resumen(tb & usr, np.where(usr, gb, 0.0), res.index),
                               "gran_bot": s63._resumen(tg & usr, np.where(usr, gg, 0.0), res.index)},
           "coeficientes": coefs, "git_sha": git_sha()}
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "resultado.json").write_text(json.dumps(jsonable(rep), indent=2, ensure_ascii=False) + "\n",
                                            encoding="utf-8")
    log(f"H67: pasa={rep['pasa']} | ΔG={comp['delta_ganancia']:+.2f} (lím. 5 % {comp['limite_inferior_5']:+.2f}) | "
        f"base {rep['base']} | gran bot {rep['gran_bot']}")
    return rep
