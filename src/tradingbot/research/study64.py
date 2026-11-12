"""Estudio 64 (pre-registro bda4760, docs/01): confirmación del gran bot con datos nuevos.

Lee `results/registro/gran5/` (todas las ventanas de 5 min de ETH y BTC desde el 2026-10-26, con la probabilidad del
gran bot congelado y la de la base) y comprueba, con ETH y BTC juntos, que el gran bot gana y que mejora a la base.
Dos miradas, cada una UNA sola vez (Bonferroni): enero (α = 0,01, desde el 2027-01-19) y abril (α = 0,04, desde el
2027-04-27, solo si enero no pasó).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from .experiment import git_sha, jsonable
from .study63 import COSTO, MARGEN, _boot_semanas, politica

REGISTRO = Path("results/registro/gran5")
SALIDA = Path("results/estudio64")
INICIO = pd.Timestamp("2026-10-26", tz="UTC")
MIRADAS = {"enero": (pd.Timestamp("2027-01-19", tz="UTC"), 0.01),
           "abril": (pd.Timestamp("2027-04-27", tz="UTC"), 0.04)}
MIN_OPS = 300
N_BOOT = 10_000
SEMILLA = 64


def cargar(registro: Path = REGISTRO, fin: pd.Timestamp | None = None) -> pd.DataFrame:
    rows = []
    for f in sorted(Path(registro).glob("*.jsonl")):
        for line in f.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                rows.append({k: r.get(k) for k in ("ventana", "moneda", "instrumento", "p_gran", "p_base", "resultado",
                                                    "fuente", "horario_usuario")})
    df = pd.DataFrame(rows, columns=["ventana", "moneda", "instrumento", "p_gran", "p_base", "resultado", "fuente",
                                     "horario_usuario"])
    if df.empty:
        return df
    df["ventana"] = pd.to_datetime(df["ventana"], utc=True)
    fin = fin if fin is not None else MIRADAS["abril"][0]
    df = df[(df["ventana"] >= INICIO) & (df["ventana"] < fin) & df["resultado"].isin([1, -1])]
    return df.drop_duplicates(["moneda", "instrumento"]).sort_values("ventana").set_index("ventana")


def dias_faltantes(registro: Path, fin: pd.Timestamp) -> list[str]:
    have = {f.stem for f in Path(registro).glob("*.jsonl")}
    return [f"{d:%Y-%m-%d}" for d in pd.date_range(INICIO, fin, freq="D", inclusive="left") if f"{d:%Y-%m-%d}" not in have]


def _resumen(toma: np.ndarray, g: np.ndarray) -> dict:
    n = int(toma.sum())
    if not n:
        return {"operaciones": 0}
    return {"operaciones": n, "acierto": float((g[toma] > 0).mean()), "ev_por_operacion": float(g[toma].mean()),
            "ganancia_total": float(g.sum())}


def evaluar(df: pd.DataFrame, alfa: float, n_boot: int = N_BOOT, seed: int = SEMILLA) -> dict:
    y = df["resultado"].to_numpy(float)
    tg, gg = politica(df["p_gran"].to_numpy(float), y)
    tb, gb = politica(df["p_base"].to_numpy(float), y)
    iso = df.index.isocalendar()
    semanas = (iso["year"].astype(int) * 100 + iso["week"].astype(int)).to_numpy()
    lim_g = float(np.quantile(_boot_semanas(gg, semanas, n_boot, seed), alfa)) if len(df) else float("nan")
    lim_d = float(np.quantile(_boot_semanas(gg - gb, semanas, n_boot, seed + 1), alfa)) if len(df) else float("nan")
    crit = {"gran_bot_gana": bool(lim_g > 0), "mejora_a_la_base": bool(lim_d > 0), "min_300": int(tg.sum()) >= MIN_OPS}
    out = {"ventanas": int(len(df)), "gran_bot": _resumen(tg, gg), "base": _resumen(tb, gb),
           "principal": {"ganancia_gran": float(gg.sum()), "limite_gran": lim_g, "delta_ganancia": float(gg.sum() - gb.sum()),
                         "limite_delta": lim_d, "alfa": alfa, "criterios": crit}}
    out["pasa"] = all(crit.values())
    out["por_moneda"] = {}
    for m in ("ETHUSDT", "BTCUSDT"):
        s = (df["moneda"] == m).to_numpy()
        out["por_moneda"][m] = {"gran_bot": _resumen(tg & s, np.where(s, gg, 0.0)),
                                "base": _resumen(tb & s, np.where(s, gb, 0.0))}
    p = df["p_gran"].to_numpy(float)
    t57 = tg & (np.maximum(p, 1 - p) >= 0.57)
    out["gran_bot_p57"] = _resumen(t57, np.where(t57, gg, 0.0))
    usr = df["horario_usuario"].fillna(False).astype(bool).to_numpy()
    out["horario_usuario"] = {"gran_bot": _resumen(tg & usr, np.where(usr, gg, 0.0)),
                              "base": _resumen(tb & usr, np.where(usr, gb, 0.0))}
    of = (df["fuente"] == "oficial").to_numpy()
    out["solo_oficial"] = {"gran_bot": _resumen(tg & of, np.where(of, gg, 0.0)), "base": _resumen(tb & of, np.where(of, gb, 0.0))}
    out["regla"] = {"costo": COSTO, "margen": MARGEN}
    return out


def run(mirada: str, registro: Path = REGISTRO, salida: Path = SALIDA, hoy: pd.Timestamp | None = None,
        n_boot: int = N_BOOT, log=print) -> dict:
    if mirada not in MIRADAS:
        raise SystemExit(f"Estudio 64: mirada «{mirada}» desconocida (enero o abril).")
    fin, alfa = MIRADAS[mirada]
    hoy = hoy or pd.Timestamp.now(tz="UTC")
    if hoy < fin:
        raise SystemExit(f"Estudio 64: la mirada de {mirada} se evalúa desde el {fin:%Y-%m-%d}; no antes.")
    salida = Path(salida)
    if (salida / f"{mirada}.json").exists():
        raise SystemExit(f"Estudio 64: la mirada de {mirada} ya se evaluó.")
    if mirada == "abril":
        previa = salida / "enero.json"
        if not previa.exists():
            raise SystemExit("Estudio 64: primero va la mirada de enero.")
        if json.loads(previa.read_text(encoding="utf-8")).get("pasa"):
            raise SystemExit("Estudio 64: ya pasó en enero; no hay mirada de abril.")
    falta = dias_faltantes(registro, fin)
    if falta:  # evaluación única: no gastarla con días sin registrar (ítem 54)
        raise SystemExit(f"Estudio 64: faltan {len(falta)} días en el registro ({', '.join(falta[:6])}…). No se evaluó.")
    rep = evaluar(cargar(registro, fin), alfa, n_boot)
    n = rep["gran_bot"].get("operaciones", 0)
    rep["veredicto"] = ("PASA" if rep["pasa"] else "sigue hasta abril" if mirada == "enero" else
                        "SIN CONCLUSIÓN (menos de 300 operaciones)" if n < MIN_OPS else "NO PASA")
    rep.update({"estudio": "Estudio 64 — confirmación del gran bot", "mirada": mirada, "git_sha": git_sha(),
                "ventanas_periodo": [str(INICIO.date()), str((fin - pd.Timedelta(days=1)).date())]})
    salida.mkdir(parents=True, exist_ok=True)
    (salida / f"{mirada}.json").write_text(json.dumps(jsonable(rep), indent=2, ensure_ascii=False) + "\n",
                                           encoding="utf-8")
    log(f"Estudio 64 ({mirada}): {rep['veredicto']} | {rep['principal']['criterios']}")
    return rep
