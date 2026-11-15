"""Estudio 70 (pre-registro ebe2874, docs/01): margen 0 los sábados y domingos (UTC) en el gran bot de OKX 5 min.

Lee `results/registro/gran5/` (todas las ventanas de 5 min de ETH y BTC desde el 2026-10-26, con la probabilidad del
gran bot congelado) y suma la ganancia de las operaciones «extra» del fin de semana: 0 ≤ p_dir − 0,5312 < 0,02.
Dos miradas, cada una UNA sola vez (Bonferroni): enero (α = 0,01, desde el 2027-01-19) y abril (α = 0,04, desde el
2027-04-27, solo si enero no pasó). `desarrollo()` reproduce las cifras *post hoc* del pre-registro.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import study64
from .experiment import git_sha, jsonable
from .study63 import COSTO, MARGEN, _boot_semanas

REGISTRO = study64.REGISTRO
SALIDA = Path("results/estudio70")
MIRADAS = study64.MIRADAS
MIN_OPS = 300
N_BOOT = 10_000
SEMILLA = 70
EPS = 1e-12
PRED_DESARROLLO = Path("results/estudio63/predicciones.parquet")


def semanas(index: pd.DatetimeIndex) -> np.ndarray:
    iso = pd.DatetimeIndex(index).isocalendar()
    return (iso["year"].astype(int) * 100 + iso["week"].astype(int)).to_numpy()


def wilson(k: int, n: int, z: float = 1.959964) -> list[float]:
    if not n:
        return [float("nan"), float("nan")]
    ph = k / n
    den = 1 + z * z / n
    c = (ph + z * z / (2 * n)) / den
    h = z * np.sqrt(ph * (1 - ph) / n + z * z / (4 * n * n)) / den
    return [float(c - h), float(c + h)]


def marcas(p: np.ndarray, y: np.ndarray, ventana: pd.DatetimeIndex) -> dict[str, np.ndarray]:
    """Lado, p_dir, ganancia si se opera, y las máscaras de la regla (inicio de ventana en UTC)."""
    lado = np.where(p >= 0.5, 1, -1)
    pdir = np.where(lado == 1, p, 1 - p)
    g = np.where(lado == np.sign(y), 1 - COSTO, -COSTO)
    finde = pd.DatetimeIndex(ventana).dayofweek.to_numpy() >= 5
    banda = (pdir - COSTO >= -EPS) & (pdir - COSTO < MARGEN - EPS)
    actual = pdir - COSTO >= MARGEN - EPS
    return {"lado": lado, "pdir": pdir, "g": g, "finde": finde, "banda": banda, "actual": actual,
            "extra": finde & banda, "control": ~finde & banda}


def _resumen(mask: np.ndarray, g: np.ndarray) -> dict:
    n = int(mask.sum())
    if not n:
        return {"operaciones": 0}
    k = int((g[mask] > 0).sum())
    return {"operaciones": n, "acierto": k / n, "wilson95": wilson(k, n), "ev_por_operacion": float(g[mask].mean()),
            "ganancia_total": float(g[mask].sum())}


def _pendiente(p: np.ndarray, y: np.ndarray) -> float | None:
    """Pendiente de la logística de y sobre logit p (1 = bien calibrado)."""
    if len(p) < 50:
        return None
    x = np.log(np.clip(p, 1e-6, 1 - 1e-6) / (1 - np.clip(p, 1e-6, 1 - 1e-6)))
    X = np.c_[np.ones(len(x)), x]
    yb = (y > 0).astype(float)
    b = np.zeros(2)
    for _ in range(50):
        q = 1 / (1 + np.exp(-X @ b))
        H = X.T @ (X * (q * (1 - q))[:, None])
        b += np.linalg.solve(H + 1e-9 * np.eye(2), X.T @ (yb - q))
    return float(b[1])


def evaluar(df: pd.DataFrame, alfa: float, n_boot: int = N_BOOT, seed: int = SEMILLA) -> dict:
    """`df` con índice = inicio de la ventana (UTC) y columnas p_gran, resultado (±1), moneda, fuente, horario_usuario."""
    y = df["resultado"].to_numpy(float)
    p = df["p_gran"].to_numpy(float)
    mk = marcas(p, y, df.index)
    g, extra = mk["g"], mk["extra"]
    lim = float(np.quantile(_boot_semanas(np.where(extra, g, 0.0), semanas(df.index), n_boot, seed), alfa)) \
        if len(df) else float("nan")
    crit = {"limite_mayor_0": bool(lim > 0), "min_300": int(extra.sum()) >= MIN_OPS}
    out = {"ventanas": int(len(df)), "extra": _resumen(extra, g),
           "principal": {"ganancia_extra": float(g[extra].sum()), "limite": lim, "alfa": alfa, "criterios": crit}}
    out["pasa"] = all(crit.values())
    dias = len(np.unique(df.index.normalize())) if len(df) else 0
    dias_finde = len(np.unique(df.index[mk["finde"]].normalize())) if mk["finde"].any() else 0
    out["regla_actual"] = _resumen(mk["actual"], g)
    out["regla_nueva"] = _resumen(mk["actual"] | extra, g)
    out["por_dia"] = {"dias": dias, "dias_fin_de_semana": dias_finde,
                      "extra_por_dia_de_fin_de_semana": (int(extra.sum()) / dias_finde) if dias_finde else None}
    out["frente_a_equilibrio"] = {"equilibrio": COSTO, **_resumen(extra, g)}
    inf: dict = {}
    for m in ("ETHUSDT", "BTCUSDT"):
        inf[m] = _resumen(extra & (df["moneda"] == m).to_numpy(), g)
    inf["al_alza"] = _resumen(extra & (mk["lado"] == 1), g)
    inf["a_la_baja"] = _resumen(extra & (mk["lado"] == -1), g)
    dow = df.index.dayofweek.to_numpy()
    inf["sabado"] = _resumen(extra & (dow == 5), g)
    inf["domingo"] = _resumen(extra & (dow == 6), g)
    usr = df["horario_usuario"].fillna(False).astype(bool).to_numpy() if "horario_usuario" in df else np.zeros(len(df), bool)
    inf["horario_usuario"] = _resumen(extra & usr, g)
    of = (df["fuente"] == "oficial").to_numpy() if "fuente" in df else np.zeros(len(df), bool)
    inf["solo_oficial"] = _resumen(extra & of, g)
    inf["control_entre_semana"] = _resumen(mk["control"], g)
    inf["pendiente_calibracion"] = {"fin_de_semana": _pendiente(p[mk["finde"]], y[mk["finde"]]),
                                    "entre_semana": _pendiente(p[~mk["finde"]], y[~mk["finde"]])}
    out["informativo"] = inf
    out["regla"] = {"costo": COSTO, "margen_entre_semana": MARGEN, "margen_fin_de_semana": 0.0,
                    "fin_de_semana": "la ventana empieza en sábado o domingo UTC"}
    return out


def run(mirada: str, registro: Path = REGISTRO, salida: Path = SALIDA, hoy: pd.Timestamp | None = None,
        n_boot: int = N_BOOT, log=print) -> dict:
    if mirada not in MIRADAS:
        raise SystemExit(f"Estudio 70: mirada «{mirada}» desconocida (enero o abril).")
    fin, alfa = MIRADAS[mirada]
    hoy = hoy or pd.Timestamp.now(tz="UTC")
    if hoy < fin:
        raise SystemExit(f"Estudio 70: la mirada de {mirada} se evalúa desde el {fin:%Y-%m-%d}; no antes.")
    salida = Path(salida)
    if (salida / f"{mirada}.json").exists():
        raise SystemExit(f"Estudio 70: la mirada de {mirada} ya se evaluó.")
    if mirada == "abril":
        previa = salida / "enero.json"
        if not previa.exists():
            raise SystemExit("Estudio 70: primero va la mirada de enero.")
        if json.loads(previa.read_text(encoding="utf-8")).get("pasa"):
            raise SystemExit("Estudio 70: ya pasó en enero; no hay mirada de abril.")
    falta = study64.dias_faltantes(registro, fin)
    if falta:  # evaluación única: no gastarla con días sin registrar (ítem 54)
        raise SystemExit(f"Estudio 70: faltan {len(falta)} días en el registro ({', '.join(falta[:6])}…). No se evaluó.")
    rep = evaluar(study64.cargar(registro, fin), alfa, n_boot)
    n = rep["extra"].get("operaciones", 0)
    rep["veredicto"] = ("PASA" if rep["pasa"] else "sigue hasta abril" if mirada == "enero" else
                        "SIN CONCLUSIÓN (menos de 300 operaciones extra)" if n < MIN_OPS else "NO PASA")
    h64 = Path("results/estudio64") / f"{mirada}.json"
    rep["h64_misma_mirada"] = json.loads(h64.read_text(encoding="utf-8")).get("pasa") if h64.exists() else None
    rep.update({"estudio": "Estudio 70 — margen 0 el fin de semana en el gran bot de OKX 5 min (pre-registro ebe2874)",
                "mirada": mirada, "git_sha": git_sha(),
                "ventanas_periodo": [str(study64.INICIO.date()), str((fin - pd.Timedelta(days=1)).date())],
                "consecuencia": "la práctica usa margen 0 el fin de semana solo si pasan H70 y H64"})
    salida.mkdir(parents=True, exist_ok=True)
    (salida / f"{mirada}.json").write_text(json.dumps(jsonable(rep), indent=2, ensure_ascii=False) + "\n",
                                           encoding="utf-8")
    log(f"Estudio 70 ({mirada}): {rep['veredicto']} | {rep['principal']['criterios']} | extra {rep['extra']}")
    return rep


def tabla_desarrollo(pred: Path = PRED_DESARROLLO) -> pd.DataFrame:
    """Predicciones fuera de muestra del Estudio 63 con el formato del registro (índice = inicio de la ventana)."""
    r = pd.read_parquet(pred)
    ventana = r.index + pd.Timedelta(minutes=1)
    return pd.DataFrame({"moneda": r["moneda"].to_numpy(), "p_gran": r["gran"].to_numpy(),
                         "resultado": r["y"].to_numpy(), "fuente": "desarrollo",
                         "horario_usuario": (ventana.hour >= 2) & (ventana.hour < 6)},
                        index=pd.DatetimeIndex(ventana, name="ventana"))


def desarrollo(pred: Path = PRED_DESARROLLO, n_boot: int = N_BOOT) -> dict:
    """Cifras post hoc del pre-registro (control: 11 051 extra, 55,18 %, +227,4, cuantil 5 % +137,9)."""
    return evaluar(tabla_desarrollo(pred), 0.05, n_boot)
