"""Estudio 60 (pre-registro 4760414, docs/01): confirmación de los contratos de 15 min de OKX (ETH y BTC).

Lee las señales que el registro diario guarda con los modelos congelados de 15 min (`results/registro/okx15_eth/`,
`okx15_btc/`) y prueba, con ETH y BTC juntos, que aciertan más que el equilibrio de 53,12 % (compra a 0,52 + comisión del
tomador). Dos miradas, cada una UNA sola vez, con α repartido (Bonferroni):
- enero: ventanas del 2026-10-26 al 2027-01-18, α = 0,01, desde el 2027-01-19;
- abril: ventanas hasta el 2027-04-26, α = 0,04, desde el 2027-04-27 (solo si enero no pasó).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from .experiment import git_sha, jsonable
from .metrics import binom_pvalue_greater, wilson
from .study56 import _boot_medias, _semanas

REGISTRO = Path("results/registro")
SALIDA = Path("results/estudio60")
MONEDAS = {"okx15_eth": "ETHUSDT", "okx15_btc": "BTCUSDT"}
INICIO = pd.Timestamp("2026-10-26", tz="UTC")
MIRADAS = {"enero": (pd.Timestamp("2027-01-19", tz="UTC"), 0.01),
           "abril": (pd.Timestamp("2027-04-27", tz="UTC"), 0.04)}
COSTO = 0.52 + 0.045 * 0.52 * 0.48  # 0,5312: equilibrio
MIN_OPS = 300
N_BOOT = 10_000
SEMILLA = 60


def cargar(registro: Path = REGISTRO, fin: pd.Timestamp | None = None) -> pd.DataFrame:
    rows = []
    for carpeta, sym in MONEDAS.items():
        for f in sorted((Path(registro) / carpeta).glob("*.jsonl")):
            for line in f.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    rows.append({**json.loads(line), "moneda": sym})
    cols = ["moneda", "ventana", "instrumento", "p", "ev_accion", "resultado", "fuente", "horario_usuario"]
    df = pd.DataFrame(rows, columns=cols)
    if df.empty:
        return df
    df["ventana"] = pd.to_datetime(df["ventana"], utc=True)
    fin = fin if fin is not None else MIRADAS["abril"][0]
    df = df[(df["ventana"] >= INICIO) & (df["ventana"] < fin) & (df["ev_accion"] >= 0.02 - 1e-9)]
    df = df[df["resultado"].isin(["gana", "pierde"])]
    return df.drop_duplicates(["moneda", "instrumento"]).sort_values("ventana").reset_index(drop=True)


def dias_faltantes(registro: Path, fin: pd.Timestamp) -> list[str]:
    falta = []
    for carpeta in MONEDAS:
        have = {f.stem for f in (Path(registro) / carpeta).glob("*.jsonl")}
        falta += [f"{carpeta}/{d:%Y-%m-%d}" for d in pd.date_range(INICIO, fin, freq="D", inclusive="left")
                  if f"{d:%Y-%m-%d}" not in have]
    return falta


def _resumen(df: pd.DataFrame) -> dict:
    n = int(len(df))
    if not n:
        return {"operaciones": 0}
    w = int((df["resultado"] == "gana").sum())
    return {"operaciones": n, "acierto": w / n, "wilson95": [float(x) for x in wilson(w, n)],
            "ganancia_media": float(w / n - COSTO)}


def evaluar(df: pd.DataFrame, alfa: float, n_boot: int = N_BOOT, seed: int = SEMILLA) -> dict:
    out = {"principal": _resumen(df)}
    n = len(df)
    if n:
        gana = (df["resultado"] == "gana").to_numpy(float)
        g = gana - COSTO
        p_valor = binom_pvalue_greater(int(gana.sum()), n, COSTO)
        lim = float(np.quantile(_boot_medias(g, _semanas(df["ventana"]), n_boot, seed), alfa))
    else:
        p_valor, lim = 1.0, float("nan")
    crit = {"min_300": n >= MIN_OPS, "p_menor_alfa": bool(p_valor < alfa), "limite_mayor_0": bool(lim > 0)}
    out["principal"].update({"p_valor": p_valor, "limite_inferior": lim, "alfa": alfa, "criterios": crit})
    out["pasa"] = all(crit.values())
    out["por_moneda"] = {m: _resumen(df[df["moneda"] == m]) for m in MONEDAS.values()}
    out["horario_usuario"] = _resumen(df[df["horario_usuario"].fillna(False).astype(bool)]) if n else {}
    out["solo_oficial"] = _resumen(df[df["fuente"] == "oficial"]) if n else {}
    out["p_058"] = _resumen(df[df["p"] >= 0.58]) if n else {}
    return out


def run(mirada: str, registro: Path = REGISTRO, salida: Path = SALIDA, hoy: pd.Timestamp | None = None,
        n_boot: int = N_BOOT, log=print) -> dict:
    if mirada not in MIRADAS:
        raise SystemExit(f"Estudio 60: mirada «{mirada}» desconocida (enero o abril).")
    fin, alfa = MIRADAS[mirada]
    hoy = hoy or pd.Timestamp.now(tz="UTC")
    if hoy < fin:
        raise SystemExit(f"Estudio 60: la mirada de {mirada} se evalúa desde el {fin:%Y-%m-%d}; no antes.")
    salida = Path(salida)
    if (salida / f"{mirada}.json").exists():
        raise SystemExit(f"Estudio 60: la mirada de {mirada} ya se evaluó.")
    if mirada == "abril":
        previa = salida / "enero.json"
        if not previa.exists():
            raise SystemExit("Estudio 60: primero va la mirada de enero.")
        if json.loads(previa.read_text(encoding="utf-8")).get("pasa"):
            raise SystemExit("Estudio 60: ya pasó en enero; no hay mirada de abril.")
    falta = dias_faltantes(registro, fin)
    if falta:  # evaluación única: no gastarla con días sin registrar (ítem 54)
        raise SystemExit(f"Estudio 60: faltan {len(falta)} días en el registro ({', '.join(falta[:6])}…). No se evaluó.")
    rep = evaluar(cargar(registro, fin), alfa, n_boot)
    n = rep["principal"]["operaciones"]
    rep["veredicto"] = ("PASA" if rep["pasa"] else "sigue hasta abril" if mirada == "enero" else
                        "SIN CONCLUSIÓN (menos de 300 señales)" if n < MIN_OPS else "NO PASA")
    rep.update({"estudio": "Estudio 60 — contratos de 15 min de OKX (ETH y BTC)", "mirada": mirada,
                "ventanas": [str(INICIO.date()), str((fin - pd.Timedelta(days=1)).date())], "git_sha": git_sha()})
    salida.mkdir(parents=True, exist_ok=True)
    (salida / f"{mirada}.json").write_text(json.dumps(jsonable(rep), indent=2, ensure_ascii=False) + "\n",
                                           encoding="utf-8")
    log(f"Estudio 60 ({mirada}): {rep['veredicto']} | {rep['principal'].get('criterios')}")
    return rep
