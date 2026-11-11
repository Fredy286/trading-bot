"""Estudio 62 (pre-registro en docs/01, 2026-11-11): el favorito dentro de la ventana en OKX (BTC, 5 min, segundo 60).

Lee el libro que graba GitHub dentro de cada ventana (`results/okx_dentro/`, `live/okx_libro_dentro.py`) y los
resultados oficiales que guarda el mismo grabador. En la foto del segundo 60, si el diferencial es ≤ 0,10 y el
favorito cuesta entre 0,60 y 0,90, se «compra» 1 contrato del favorito. Ganancia = 1 si gana − precio − comisión del
tomador. Se evalúa UNA sola vez, desde el 2026-12-13.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from .experiment import git_sha, jsonable

DATOS = Path("results/okx_dentro")
SALIDA = Path("results/estudio62")
INICIO = pd.Timestamp("2026-11-12", tz="UTC")
FIN = pd.Timestamp("2026-12-12", tz="UTC")  # excluido
EVALUAR_DESDE = pd.Timestamp("2026-12-13", tz="UTC")
SERIE = "BTC-UPDOWN-5MIN"
SEG = 60
DIF_MAX, P_MIN, P_MAX = 0.10, 0.60, 0.90
K_TOMADOR = 0.045
MIN_OPS = 300
ALFA = 0.05
N_BOOT = 10_000
SEMILLA = 62


def cargar_fotos(datos: Path = DATOS) -> pd.DataFrame:
    """Una fila por (contrato, segundo): la primera foto de GitHub sin error, por orden de archivo."""
    filas, vistos = [], set()
    for f in sorted(Path(datos).glob("*.jsonl")):
        if f.name.endswith("_resultados.jsonl"):
            continue
        for line in f.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            x = json.loads(line)
            if x.get("fuente") != "github" or "error" in x or not x.get("a") or not x.get("b"):
                continue
            k = (x["inst"], x["seg"])
            if k in vistos:
                continue
            vistos.add(k)
            inicio = pd.Timestamp(x["objetivo"]) - pd.Timedelta(seconds=int(x["seg"]))
            filas.append({"inst": x["inst"], "seg": int(x["seg"]), "dur": int(x["dur"]), "moneda": x["moneda"],
                          "inicio": inicio, "a": x["a"], "b": x["b"]})
    return pd.DataFrame(filas, columns=["inst", "seg", "dur", "moneda", "inicio", "a", "b"])


def cargar_resultados(datos: Path = DATOS) -> dict[str, int]:
    """Contrato → 1 si ganó «Al alza», 0 si «A la baja» (resultado oficial de OKX)."""
    out = {}
    for f in sorted(Path(datos).glob("*_resultados.jsonl")):
        for line in f.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                if str(r.get("resultado")) in ("1", "2"):
                    out.setdefault(r["inst"], 1 if str(r["resultado"]) == "1" else 0)
    return out


def favorito(a: list, b: list) -> tuple[int, float, float] | None:
    """(lado: 1 «Al alza» / 0 «A la baja», precio medio de 1 contrato, precio medio del libro) según la regla, o None."""
    if not a or not b or a[0][0] - b[0][0] > DIF_MAX + 1e-9:
        return None
    mid = (a[0][0] + b[0][0]) / 2
    lado = 1 if mid >= 0.5 else 0
    niveles = sorted((float(p), float(s)) for p, s in a) if lado else sorted((round(1 - float(p), 6), float(s)) for p, s in b)
    if not (P_MIN - 1e-9 <= niveles[0][0] <= P_MAX + 1e-9):
        return None
    falta, pagado = 1.0, 0.0
    for p, s in niveles:
        if p > P_MAX + 1e-9:
            break
        q = min(s, falta)
        pagado += q * p
        falta -= q
        if falta <= 1e-12:
            return lado, pagado, (mid if lado else 1 - mid)
    return None


def operaciones(fotos: pd.DataFrame, res: dict[str, int]) -> tuple[pd.DataFrame, dict]:
    f = fotos[(fotos["inst"].str.startswith(SERIE + "-")) & (fotos["seg"] == SEG) &
              (fotos["inicio"] >= INICIO) & (fotos["inicio"] < FIN)]
    filas, sin_res = [], 0
    for x in f.itertuples(index=False):
        fav = favorito(x.a, x.b)
        if fav is None:
            continue
        if x.inst not in res:
            sin_res += 1
            continue
        lado, precio, medio = fav
        gana = float(res[x.inst] == lado)
        filas.append({"inicio": x.inicio, "lado": lado, "precio": precio, "medio": medio, "gana": gana,
                      "ganancia": gana - precio - K_TOMADOR * precio * (1 - precio)})
    cob = {"ventanas_con_foto": int(len(f)), "esperadas": int((FIN - INICIO) / pd.Timedelta(minutes=5)),
           "favoritas_sin_resultado": sin_res}
    return pd.DataFrame(filas, columns=["inicio", "lado", "precio", "medio", "gana", "ganancia"]), cob


def _resumen(o: pd.DataFrame) -> dict:
    if o.empty:
        return {"operaciones": 0}
    return {"operaciones": int(len(o)), "acierto": float(o["gana"].mean()), "precio_medio": float(o["precio"].mean()),
            "ganancia_media": float(o["ganancia"].mean()),
            "ganancia_al_medio": float((o["gana"] - o["medio"]).mean())}


def _boot_dias(x: np.ndarray, dias: np.ndarray, n_boot: int, seed: int) -> np.ndarray:
    ds, inv = np.unique(dias, return_inverse=True)
    sumas = np.bincount(inv, weights=x, minlength=len(ds))
    cuentas = np.bincount(inv, minlength=len(ds)).astype(float)
    idx = np.random.default_rng(seed).integers(0, len(ds), size=(n_boot, len(ds)))
    return sumas[idx].sum(axis=1) / np.maximum(cuentas[idx].sum(axis=1), 1)


def calibracion(fotos: pd.DataFrame, res: dict[str, int]) -> list[dict]:
    """Informativo: frecuencia de «Al alza» frente al precio medio, por contrato y segundo, con diferencial ≤ 0,10."""
    f = fotos[(fotos["inicio"] >= INICIO) & (fotos["inicio"] < FIN)]
    filas = []
    for x in f.itertuples(index=False):
        if x.inst in res and x.a[0][0] - x.b[0][0] <= DIF_MAX + 1e-9:
            filas.append({"serie": x.inst.rsplit("-", 3)[0], "seg": x.seg, "medio": (x.a[0][0] + x.b[0][0]) / 2,
                          "sube": res[x.inst]})
    d = pd.DataFrame(filas, columns=["serie", "seg", "medio", "sube"])
    if d.empty:
        return []
    d["tramo"] = pd.cut(d["medio"], [0, .1, .2, .3, .4, .6, .7, .8, .9, 1.0])
    t = d.groupby(["serie", "seg", "tramo"], observed=True).agg(n=("sube", "size"), medio=("medio", "mean"),
                                                                 sube=("sube", "mean")).reset_index()
    t["tramo"] = t["tramo"].astype(str)
    return t.to_dict(orient="records")


def evaluar(fotos: pd.DataFrame, res: dict[str, int], n_boot: int = N_BOOT, seed: int = SEMILLA) -> dict:
    o, cob = operaciones(fotos, res)
    out = {"cobertura": cob, "principal": _resumen(o)}
    n = len(o)
    g = o["ganancia"].to_numpy(float)
    if n >= 2 and g.std(ddof=1) > 0:
        z = g.mean() / (g.std(ddof=1) / math.sqrt(n))
        p_valor = 0.5 * math.erfc(z / math.sqrt(2))
        lim = float(np.quantile(_boot_dias(g, o["inicio"].dt.floor("D").astype("int64").to_numpy(), n_boot, seed), ALFA))
    else:
        p_valor, lim = float("nan"), float("nan")
    crit = {"min_300": n >= MIN_OPS, "p_menor_005": bool(p_valor < ALFA), "limite_mayor_0": bool(lim > 0)}
    out["principal"].update({"p_valor": p_valor, "limite_inferior_5": lim, "criterios": crit})
    out["pasa"] = all(crit.values())
    out["veredicto"] = "PASA" if out["pasa"] else ("SIN CONCLUSIÓN (menos de 300 operaciones)" if n < MIN_OPS else "NO PASA")
    tramos = pd.cut(o["precio"], [0.6, 0.7, 0.8, 0.9], include_lowest=True) if n else []
    out["por_tramo"] = {str(k): _resumen(v) for k, v in o.groupby(tramos, observed=True)} if n else {}
    out["horario_usuario"] = _resumen(o[(o["inicio"].dt.hour >= 2) & (o["inicio"].dt.hour < 6)]) if n else {}
    out["calibracion"] = calibracion(fotos, res)
    return out


def run(datos: Path = DATOS, salida: Path = SALIDA, hoy: pd.Timestamp | None = None, n_boot: int = N_BOOT,
        log=print) -> dict:
    hoy = hoy or pd.Timestamp.now(tz="UTC")
    if hoy < EVALUAR_DESDE:
        raise SystemExit(f"Estudio 62: se evalúa desde el {EVALUAR_DESDE:%Y-%m-%d}; no antes.")
    salida = Path(salida)
    if (salida / "resultado.json").exists():
        raise SystemExit("Estudio 62: ya se evaluó (evaluación única).")
    rep = evaluar(cargar_fotos(datos), cargar_resultados(datos), n_boot)
    rep.update({"estudio": "Estudio 62 — el favorito dentro de la ventana en OKX (BTC 5 min, segundo 60)",
                "ventanas": [str(INICIO), str(FIN)], "git_sha": git_sha()})
    salida.mkdir(parents=True, exist_ok=True)
    (salida / "resultado.json").write_text(json.dumps(jsonable(rep), indent=2, ensure_ascii=False) + "\n",
                                           encoding="utf-8")
    log(f"Estudio 62: {rep['veredicto']} | {rep['principal']}")
    return rep
