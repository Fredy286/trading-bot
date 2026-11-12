"""Estudio 66 (pre-registro 0e10605, docs/01): el gran bot del blitz de BTC de IQ Option (3 min, pago 86 %).

Ocho opiniones por vela (todas fuera de muestra, hasta el segundo 49): p42 (propia), p51 y p53 (ETH y SOL a 3 min),
p20 (BTC 1 min) y las de 1 min del Estudio 26 (ETH, SOL, XRP, DOGE). Etiqueta y regla de operar del Estudio 42.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import apilado
from . import study63 as s63
from .contracts import BinaryContract
from .experiment import git_sha, jsonable
from .study65 import E26

FUENTES = {"p51": Path("results/estudio51/predicciones.parquet"), "p53": Path("results/estudio53/predicciones.parquet"),
           "p20": Path("results/estudio20/predicciones.parquet"), **E26}
P42 = Path("results/estudio42/predicciones.parquet")
OPINIONES = ("propia", "p51", "p53", "p20", *E26)
PAGO, MARGEN = 0.86, 0.02
N_BOOT = 10_000
SEMILLA = 66


def tabla(p42: Path = P42, fuentes: dict | None = None) -> pd.DataFrame:
    b = pd.read_parquet(p42)
    df = pd.DataFrame({"propia": b["p"], "y": b["y"], "q": b["q"]}, index=b.index)
    for k, f in (fuentes or FUENTES).items():
        df[k] = pd.read_parquet(f)["p"].reindex(df.index)
    df = df[(df.index >= s63.INICIO) & (df.index < s63.FIN)]
    return df.dropna(subset=[*OPINIONES, "y", "q"])


def politica(p: np.ndarray, q: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    lado = np.where(p >= 0.5, 1, -1)
    pdir = np.where(lado == 1, p, 1 - p)
    toma = BinaryContract(PAGO, "refund").ev(pdir, q) >= MARGEN
    r = lado * np.sign(y)
    return toma, np.where(toma, np.where(r > 0, PAGO, np.where(r < 0, -1.0, 0.0)), 0.0)


def _resumen(toma, g, index) -> dict:
    n = int(toma.sum())
    if not n:
        return {"operaciones": 0}
    dias = max((index.max() - index.min()).days + 1, 1)
    dec = toma & (g != 0)
    return {"operaciones": n, "por_dia": n / dias, "acierto_sin_empates": float((g[dec] > 0).mean()) if dec.any() else None,
            "ev_por_operacion": float(g[toma].mean()), "ganancia_total": float(g.sum())}


def run(out_dir: Path = Path("results/estudio66"), n_boot: int = N_BOOT, log=print, p42: Path = P42,
        fuentes: dict | None = None) -> dict:
    df = tabla(p42, fuentes)
    gran, coefs = apilado.walk_forward(df, OPINIONES, ajustar=(df["y"].to_numpy() != 0))
    res = df.assign(gran=gran).dropna(subset=["gran"])
    y, q = res["y"].to_numpy(), res["q"].to_numpy()
    tg, gg = politica(res["gran"].to_numpy(), q, y)
    tb, gb = politica(res["propia"].to_numpy(), q, y)
    comp = apilado.comparar(gg, gb, res.index, n_boot, SEMILLA)
    crit = {"limite_5_mayor_0": comp["limite_inferior_5"] > 0, "min_300": int(tg.sum()) >= 300}
    dec = y != 0
    ll_b = s63._logloss(res["propia"].to_numpy()[dec], y[dec])
    ll_g = s63._logloss(res["gran"].to_numpy()[dec], y[dec])
    usr = (res.index.hour >= 2) & (res.index.hour < 6)
    rep = {"estudio": "Estudio 66 — gran bot del blitz de BTC (pre-registro 0e10605)", "filas": int(len(res)),
           "principal": {**comp, "criterios": crit}, "pasa": all(crit.values()),
           "base": _resumen(tb, gb, res.index), "gran_bot": _resumen(tg, gg, res.index),
           "logloss_sin_empates": {"base": float(ll_b.mean()), "gran_bot": float(ll_g.mean())},
           "horario_usuario": {"base": _resumen(tb & usr, np.where(usr, gb, 0.0), res.index),
                               "gran_bot": _resumen(tg & usr, np.where(usr, gg, 0.0), res.index)},
           "coeficientes": coefs, "git_sha": git_sha()}
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "resultado.json").write_text(json.dumps(jsonable(rep), indent=2, ensure_ascii=False) + "\n",
                                            encoding="utf-8")
    log(f"H66: pasa={rep['pasa']} | ΔG={comp['delta_ganancia']:+.2f} (lím. 5 % {comp['limite_inferior_5']:+.2f}) | "
        f"base {rep['base']} | gran bot {rep['gran_bot']}")
    return rep
