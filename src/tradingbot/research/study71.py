"""Estudio 71 (pre-registro ebe2874, docs/01): apoyo del gran bot de 15 min para el contrato de 5 min de OKX, de lunes
a viernes.

Se compra el contrato de 5 min cuando la ventana empieza de lunes a viernes UTC en el minuto 0, 15, 30 o 45, el gran
bot de 15 min de la misma moneda da señal en la ventana de 15 min que empieza a la vez, el de 5 min apunta al mismo
lado y el de 5 min solo no llegaba al margen (0 ≤ p_dir5 − 0,5312 < 0,02). Va en secuencia fija detrás del
Estudio 70: en cada mirada solo se evalúa si H70 ya pasó (en esa mirada o en la de enero).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import study64, study70
from .experiment import git_sha, jsonable
from .study63 import COSTO, MARGEN, _boot_semanas

REGISTRO5 = study64.REGISTRO
REGISTRO15 = Path("results/registro/gran15")
SALIDA = Path("results/estudio71")
SALIDA70 = study70.SALIDA
MIRADAS = study64.MIRADAS
MIN_OPS = 300
N_BOOT = 10_000
SEMILLA = 71
EPS = 1e-12


def cargar15(registro: Path = REGISTRO15, fin: pd.Timestamp | None = None) -> pd.DataFrame:
    """Opinión del gran bot de 15 min por ventana y moneda (no hace falta su resultado)."""
    rows = []
    for f in sorted(Path(registro).glob("*.jsonl")):
        for line in f.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                rows.append({k: r.get(k) for k in ("ventana", "moneda", "instrumento", "p_gran", "senal_gran")})
    df = pd.DataFrame(rows, columns=["ventana", "moneda", "instrumento", "p_gran", "senal_gran"])
    if df.empty:
        return df.set_index("ventana")
    df["ventana"] = pd.to_datetime(df["ventana"], utc=True)
    fin = fin if fin is not None else MIRADAS["abril"][0]
    df = df[(df["ventana"] >= study64.INICIO) & (df["ventana"] < fin)]
    return df.drop_duplicates(["moneda", "instrumento"]).sort_values("ventana").set_index("ventana")


def unir(df5: pd.DataFrame, df15: pd.DataFrame, desfase_min: int = 0) -> pd.DataFrame:
    """A cada ventana de 5 min le pega la opinión de 15 min del bloque que empezó `desfase_min` antes (0 = alineada)."""
    a = df5.reset_index()
    b = df15.reset_index()[["ventana", "moneda", "p_gran", "senal_gran"]].rename(
        columns={"p_gran": "p15", "senal_gran": "senal15"})
    b["ventana"] = b["ventana"] + pd.Timedelta(minutes=desfase_min)
    j = a.merge(b, on=["ventana", "moneda"], how="left")
    return j.set_index("ventana").sort_index()


def regla(j: pd.DataFrame, desfase_min: int = 0) -> tuple[np.ndarray, np.ndarray]:
    """(se compra, ganancia del contrato de 5 min) con la regla congelada."""
    v = pd.DatetimeIndex(j.index)
    p5 = j["p_gran"].to_numpy(float)
    y = j["resultado"].to_numpy(float)
    p15 = j["p15"].to_numpy(float)
    l5 = np.where(p5 >= 0.5, 1, -1)
    pd5 = np.where(l5 == 1, p5, 1 - p5)
    l15 = np.where(p15 >= 0.5, 1, -1)
    pd15 = np.where(l15 == 1, p15, 1 - p15)
    s15 = j["senal15"].map(lambda x: None if x is None or (isinstance(x, float) and np.isnan(x)) else bool(x))
    calc = pd15 - COSTO >= MARGEN - EPS  # si el registro no trae el campo, se calcula igual que gran_bot.filas_15
    sen15 = np.where(s15.isna().to_numpy(), calc, s15.fillna(False).astype(bool).to_numpy()) & ~np.isnan(p15)
    alin = (v.minute.to_numpy() % 15) == (desfase_min % 15)
    lab = v.dayofweek.to_numpy() < 5
    banda5 = (pd5 - COSTO >= -EPS) & (pd5 - COSTO < MARGEN - EPS)
    toma = alin & lab & sen15 & (l5 == l15) & banda5
    g = np.where(l5 == np.sign(y), 1 - COSTO, -COSTO)
    return toma, g


def _resumen(mask: np.ndarray, g: np.ndarray) -> dict:
    return study70._resumen(mask, g)


def evaluar(df5: pd.DataFrame, df15: pd.DataFrame, alfa: float, n_boot: int = N_BOOT, seed: int = SEMILLA) -> dict:
    j = unir(df5, df15)
    toma, g = regla(j)
    lim = float(np.quantile(_boot_semanas(np.where(toma, g, 0.0), study70.semanas(j.index), n_boot, seed), alfa)) \
        if len(j) else float("nan")
    crit = {"limite_mayor_0": bool(lim > 0), "min_300": int(toma.sum()) >= MIN_OPS}
    out = {"ventanas_5min": int(len(j)), "operaciones": _resumen(toma, g),
           "principal": {"ganancia": float(g[toma].sum()), "limite": lim, "alfa": alfa, "criterios": crit}}
    out["pasa"] = all(crit.values())
    lab = j.index.dayofweek < 5
    dias_lab = len(np.unique(j.index[lab].normalize())) if lab.any() else 0
    inf: dict = {"por_dia_laborable": (int(toma.sum()) / dias_lab) if dias_lab else None}
    for k, des in (("segunda_ventana_del_bloque", 5), ("tercera_ventana_del_bloque", 10)):
        jj = unir(df5, df15, des)
        t2, g2 = regla(jj, des)
        inf[k] = _resumen(t2, g2)
    for m in ("ETHUSDT", "BTCUSDT"):
        inf[m] = _resumen(toma & (j["moneda"] == m).to_numpy(), g)
    usr = j["horario_usuario"].fillna(False).astype(bool).to_numpy() if "horario_usuario" in j else np.zeros(len(j), bool)
    inf["horario_usuario"] = _resumen(toma & usr, g)
    of = (j["fuente"] == "oficial").to_numpy() if "fuente" in j else np.zeros(len(j), bool)
    inf["solo_oficial"] = _resumen(toma & of, g)
    out["informativo"] = inf
    return out


def _h70_paso(mirada: str, salida70: Path) -> bool:
    previas = ["enero"] if mirada == "enero" else ["enero", "abril"]
    necesaria = Path(salida70) / f"{mirada}.json"
    if mirada == "enero" and not necesaria.exists():
        raise SystemExit("Estudio 71: primero va la mirada de enero del Estudio 70.")
    if mirada == "abril":
        ene = Path(salida70) / "enero.json"
        if not ene.exists():
            raise SystemExit("Estudio 71: primero va la mirada de enero del Estudio 70.")
        if not json.loads(ene.read_text(encoding="utf-8")).get("pasa") and not necesaria.exists():
            raise SystemExit("Estudio 71: primero va la mirada de abril del Estudio 70.")
    return any((Path(salida70) / f"{m}.json").exists()
               and json.loads((Path(salida70) / f"{m}.json").read_text(encoding="utf-8")).get("pasa") for m in previas)


def run(mirada: str, registro5: Path = REGISTRO5, registro15: Path = REGISTRO15, salida: Path = SALIDA,
        salida70: Path = SALIDA70, hoy: pd.Timestamp | None = None, n_boot: int = N_BOOT, log=print) -> dict:
    if mirada not in MIRADAS:
        raise SystemExit(f"Estudio 71: mirada «{mirada}» desconocida (enero o abril).")
    fin, alfa = MIRADAS[mirada]
    hoy = hoy or pd.Timestamp.now(tz="UTC")
    if hoy < fin:
        raise SystemExit(f"Estudio 71: la mirada de {mirada} se evalúa desde el {fin:%Y-%m-%d}; no antes.")
    salida = Path(salida)
    if (salida / f"{mirada}.json").exists():
        raise SystemExit(f"Estudio 71: la mirada de {mirada} ya se evaluó.")
    if mirada == "abril":
        previa = salida / "enero.json"
        if previa.exists() and json.loads(previa.read_text(encoding="utf-8")).get("pasa"):
            raise SystemExit("Estudio 71: ya pasó en enero; no hay mirada de abril.")
    base = {"estudio": "Estudio 71 — apoyo del gran bot de 15 min para el contrato de 5 min (pre-registro ebe2874)",
            "mirada": mirada, "git_sha": git_sha(),
            "ventanas_periodo": [str(study64.INICIO.date()), str((fin - pd.Timedelta(days=1)).date())]}
    if not _h70_paso(mirada, salida70):
        rep = {**base, "evaluada": False, "pasa": False, "veredicto": "NO EVALUADA (H70 no ha pasado)"}
    else:
        for reg in (registro5, registro15):
            falta = study64.dias_faltantes(reg, fin)
            if falta:
                raise SystemExit(f"Estudio 71: faltan {len(falta)} días en {reg} ({', '.join(falta[:6])}…). No se evaluó.")
        rep = {**base, "evaluada": True, **evaluar(study64.cargar(registro5, fin), cargar15(registro15, fin), alfa, n_boot)}
        n = rep["operaciones"].get("operaciones", 0)
        rep["veredicto"] = ("PASA" if rep["pasa"] else "sigue hasta abril" if mirada == "enero" else
                            "SIN CONCLUSIÓN (menos de 300 operaciones)" if n < MIN_OPS else "NO PASA")
    rep["consecuencia"] = "la práctica añade la regla de lunes a viernes solo si pasan H71, H64 y H69"
    salida.mkdir(parents=True, exist_ok=True)
    (salida / f"{mirada}.json").write_text(json.dumps(jsonable(rep), indent=2, ensure_ascii=False) + "\n",
                                           encoding="utf-8")
    log(f"Estudio 71 ({mirada}): {rep['veredicto']}")
    return rep


def desarrollo(n_boot: int = N_BOOT) -> dict:
    """Cifras post hoc del pre-registro (control: 4 188 operaciones, 55,06 %, +81,2, cuantil 5 % +14,6).

    Regenera en memoria el walk-forward del Estudio 67 (control +484,1) y lo une con las predicciones del 63."""
    from . import apilado, study63 as s63, study67 as s67

    p54 = pd.read_parquet(s63.P54)
    otras = {k: pd.read_parquet(f)["p"] for k, f in s63.FUENTES.items()}
    partes = []
    for m in s63.MONEDAS:
        df = s67.tabla(m, p54, otras)
        gran, _ = apilado.walk_forward(df, s67.OPINIONES)
        x = df.assign(gran=gran).dropna(subset=["gran"])
        partes.append(pd.DataFrame({"moneda": m, "p_gran": x["gran"].to_numpy(), "senal_gran": None},
                                   index=pd.DatetimeIndex(x.index + pd.Timedelta(minutes=1), name="ventana")))
    df15 = pd.concat(partes).sort_index()
    return evaluar(study70.tabla_desarrollo(), df15, 0.05, n_boot)
