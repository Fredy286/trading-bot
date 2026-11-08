"""Estudio 56 (pre-registro en docs/01, 2026-11-08): ¿las señales de OKX siguen ganando al precio que de verdad se
puede comprar?

Une las señales del registro diario (`results/registro/okx_eth|okx_btc/`, modelos congelados del Estudio 55) con el
libro de órdenes que graba GitHub (`results/okx_libro/`, `live/okx_libro.py`) por nombre de contrato. Cada señal se
«compra» (1 contrato) al precio del libro 10 s antes de la ventana, que es cuando sale el aviso, si ese precio es
≤ 0,53. Ganancia por contrato = 1 si acierta − (precio + comisión del tomador).

Dos miradas, cada una UNA sola vez, con α repartido (Bonferroni):
- enero: ventanas del 2026-11-09 al 2027-01-18, α = 0,01, después del 2027-01-19;
- abril: ventanas del 2026-11-09 al 2027-04-26, α = 0,04, después del 2027-04-27 (solo si enero no pasó).
Antes de esas fechas `run` se niega a evaluar (salvo en las pruebas, que pasan `hoy`).
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from .experiment import git_sha, jsonable

REGISTRO = Path("results/registro")
LIBRO = Path("results/okx_libro")
SALIDA = Path("results/estudio56")
MONEDAS = {"okx_eth": "ETHUSDT", "okx_btc": "BTCUSDT"}
INICIO = pd.Timestamp("2026-11-09", tz="UTC")
# mirada → (fin exclusivo de las ventanas = primer día en que se puede evaluar, α)
MIRADAS = {"enero": (pd.Timestamp("2027-01-19", tz="UTC"), 0.01),
           "abril": (pd.Timestamp("2027-04-27", tz="UTC"), 0.04)}
PRECIO_MAX = 0.53
K_TOMADOR = 0.045
COSTO_REF = 0.52 + K_TOMADOR * 0.52 * 0.48  # lo que supone el Estudio 55
MIN_OPS = 500
N_BOOT = 10_000
SEMILLA = 56
FOTO = -10  # segundos antes de la ventana: cuando sale el aviso
FOTOS_EXTRA = (-7, -5, -3)  # informativo: si el clic llega más tarde


def costo(precio):
    """Precio + comisión del tomador (0,045 × P × (1 − P)); gana 1 USDT si acierta."""
    return precio + K_TOMADOR * precio * (1 - precio)


def precio_un_contrato(foto: dict, lado: str, cantidad: float = 1.0, tope: float = PRECIO_MAX):
    """(precio medio para comprar `cantidad` contratos del `lado`, contratos disponibles a ≤ `tope`).
    «Up» compra en las ventas («a»); «Down» cuesta 1 − cada compra («b»). Precio None si no alcanza a ≤ `tope`."""
    if lado == "Up":
        niveles = sorted((float(p), float(s)) for p, s in foto.get("a") or [])
    else:
        niveles = sorted((round(1 - float(p), 6), float(s)) for p, s in foto.get("b") or [])
    dentro = [(p, s) for p, s in niveles if p <= tope + 1e-9]
    disponible = sum(s for _, s in dentro)
    falta, pagado = cantidad, 0.0
    for p, s in dentro:
        q = min(s, falta)
        pagado += q * p
        falta -= q
        if falta <= 1e-12:
            return pagado / cantidad, disponible
    return None, disponible


def cargar_libro(directorio: Path = LIBRO) -> dict[str, dict]:
    """Nombre del contrato → {segundo: foto}. Solo grabaciones de GitHub; si una ventana quedó grabada dos veces, la
    primera (por nombre de archivo) que tenga la foto de −10 s sin error."""
    out: dict[str, dict] = {}
    for f in sorted(Path(directorio).glob("*.jsonl")):
        for line in f.read_text(encoding="utf-8").splitlines():
            try:
                fila = json.loads(line) if line.strip() else None
            except json.JSONDecodeError:
                fila = None
            if not fila or fila.get("fuente") != "github":
                continue
            for sym in MONEDAS.values():
                x = fila.get(sym) or {}
                if not x.get("inst"):
                    continue
                fotos = {int(ft["seg"]): ft for ft in x.get("fotos") or []}
                valida = FOTO in fotos and "error" not in fotos[FOTO]
                if x["inst"] not in out or (valida and not out[x["inst"]]["valida"]):
                    out[x["inst"]] = {"fotos": fotos, "valida": valida}
    return out


def cargar_senales(registro: Path = REGISTRO, fin: pd.Timestamp | None = None) -> pd.DataFrame:
    """Señales registradas de ETH y BTC con ventana en [INICIO, fin)."""
    rows = []
    for carpeta, sym in MONEDAS.items():
        for f in sorted((Path(registro) / carpeta).glob("*.jsonl")):
            for line in f.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    rows.append({**json.loads(line), "moneda": sym})
    cols = ["moneda", "ventana", "instrumento", "lado", "p", "ev_accion", "resultado", "horario_usuario"]
    df = pd.DataFrame(rows, columns=cols)
    if df.empty:
        return df
    df["ventana"] = pd.to_datetime(df["ventana"], utc=True)
    df = df[(df["ventana"] >= INICIO) & (df["ventana"] < (fin if fin is not None else MIRADAS["abril"][0]))]
    df = df[df["ev_accion"] >= 0.02 - 1e-9]  # la regla del Estudio 55 (el registro ya solo guarda esas)
    return df.drop_duplicates(["moneda", "instrumento"]).sort_values("ventana").reset_index(drop=True)


def dias_faltantes(registro: Path, fin: pd.Timestamp) -> list[str]:
    """Días de [INICIO, fin) sin archivo del registro, en cualquiera de las dos monedas."""
    falta = []
    for carpeta in MONEDAS:
        have = {f.stem for f in (Path(registro) / carpeta).glob("*.jsonl")}
        falta += [f"{carpeta}/{d:%Y-%m-%d}" for d in pd.date_range(INICIO, fin, freq="D", inclusive="left")
                  if f"{d:%Y-%m-%d}" not in have]
    return falta


def _semanas(t: pd.Series) -> np.ndarray:
    iso = pd.DatetimeIndex(t).isocalendar()
    return (iso["year"].astype(int) * 100 + iso["week"].astype(int)).to_numpy()


def _boot_medias(x: np.ndarray, semanas: np.ndarray, n_boot: int, seed: int) -> np.ndarray:
    """Medias de `x` remuestreando semanas ISO completas con reemplazo."""
    ws, inv = np.unique(semanas, return_inverse=True)
    sumas = np.bincount(inv, weights=x, minlength=len(ws))
    cuentas = np.bincount(inv, minlength=len(ws)).astype(float)
    idx = np.random.default_rng(seed).integers(0, len(ws), size=(n_boot, len(ws)))
    return sumas[idx].sum(axis=1) / np.maximum(cuentas[idx].sum(axis=1), 1)


def _resumen(df: pd.DataFrame) -> dict:
    if df.empty:
        return {"operaciones": 0}
    g = df["ganancia"].to_numpy(float)
    return {"operaciones": int(len(df)), "acierto": float(df["gana"].mean()), "ganancia_media": float(g.mean()),
            "precio_medio": float(df["precio"].mean()),
            "ganancia_con_052": float((df["gana"] - COSTO_REF).mean())}


def evaluar(senales: pd.DataFrame, libro: dict, alfa: float, n_boot: int = N_BOOT, seed: int = SEMILLA) -> dict:
    filas = []
    for r in senales.itertuples(index=False):
        x = libro.get(r.instrumento)
        fila = {"moneda": r.moneda, "ventana": r.ventana, "lado": r.lado, "p": r.p, "resultado": r.resultado,
                "horario_usuario": bool(r.horario_usuario)}
        for seg in (FOTO, *FOTOS_EXTRA):
            foto = x["fotos"].get(seg) if x else None
            if foto is None or "error" in foto:
                fila[f"estado{seg}"], fila[f"precio{seg}"], fila[f"disp{seg}"] = "sin foto", None, None
            else:
                precio, disp = precio_un_contrato(foto, r.lado)
                fila[f"estado{seg}"] = "comprada" if precio is not None else "bloqueada"
                fila[f"precio{seg}"], fila[f"disp{seg}"] = precio, disp
        filas.append(fila)
    df = pd.DataFrame(filas)
    out: dict = {"senales": int(len(df))}
    if df.empty:
        return {**out, "veredicto": "sin datos"}
    df["gana"] = (df["resultado"] == "gana").astype(float)
    con_res = df[df["resultado"].isin(["gana", "pierde"])].copy()
    out["sin_resultado"] = int(len(df) - len(con_res))
    out["cobertura"] = {m: {e: int(((con_res["moneda"] == m) & (con_res[f"estado{FOTO}"] == e)).sum())
                            for e in ("comprada", "bloqueada", "sin foto")} for m in MONEDAS.values()}

    def compradas(seg):
        c = con_res[con_res[f"estado{seg}"] == "comprada"].copy()
        c["precio"] = c[f"precio{seg}"].astype(float)
        c["ganancia"] = c["gana"] - costo(c["precio"])
        return c

    comp = compradas(FOTO)
    n = len(comp)
    g = comp["ganancia"].to_numpy(float)
    principal = _resumen(comp)
    if n >= 2:
        sd = float(g.std(ddof=1))
        z = float(g.mean() / (sd / math.sqrt(n))) if sd > 0 else float("inf") * np.sign(g.mean())
        p_valor = 0.5 * math.erfc(z / math.sqrt(2))
        medias = _boot_medias(g, _semanas(comp["ventana"]), n_boot, seed)
        lim = float(np.quantile(medias, alfa))
    else:
        p_valor, lim = float("nan"), float("nan")
    criterios = {"min_500": n >= MIN_OPS, "p_menor_alfa": bool(p_valor < alfa), "limite_mayor_0": bool(lim > 0)}
    out["principal"] = {**principal, "p_valor": p_valor, "limite_inferior": lim, "alfa": alfa, "criterios": criterios}
    out["pasa"] = all(criterios.values())

    # informativo (pre-registrado, sin veredicto)
    out["por_moneda"] = {m: _resumen(comp[comp["moneda"] == m]) for m in MONEDAS.values()}
    out["horario_usuario"] = _resumen(comp[comp["horario_usuario"]])
    out["clic_mas_tarde"] = {str(s): _resumen(compradas(s)) for s in FOTOS_EXTRA}
    con_foto = con_res[con_res[f"estado{FOTO}"] != "sin foto"]
    bloq = con_foto[con_foto[f"estado{FOTO}"] == "bloqueada"]
    out["bloqueadas_por_precio"] = {"fraccion": float(len(bloq) / len(con_foto)) if len(con_foto) else None,
                                    "por_moneda": {m: float((bloq["moneda"] == m).sum() / max((con_foto["moneda"] == m).sum(), 1))
                                                   for m in MONEDAS.values()}}
    if len(bloq) and n:  # selección adversa: ¿aciertan más las que el libro deja caras?
        ac_c, ac_b = float(comp["gana"].mean()), float(bloq["gana"].mean())
        todas = pd.concat([comp.assign(grupo=1.0), bloq.assign(grupo=0.0)])
        sem = _semanas(todas["ventana"])
        ws, inv = np.unique(sem, return_inverse=True)
        rng = np.random.default_rng(seed + 1)
        idx = rng.integers(0, len(ws), size=(min(n_boot, 4000), len(ws)))
        dif = []
        for fila_idx in idx:
            peso = np.bincount(fila_idx, minlength=len(ws))[inv]
            pc, pb = peso * todas["grupo"].to_numpy(), peso * (1 - todas["grupo"].to_numpy())
            if pc.sum() and pb.sum():
                dif.append((pc * todas["gana"]).sum() / pc.sum() - (pb * todas["gana"]).sum() / pb.sum())
        out["seleccion_adversa"] = {"acierto_compradas": ac_c, "acierto_bloqueadas": ac_b, "diferencia": ac_c - ac_b,
                                    "ic95": [float(np.quantile(dif, 0.025)), float(np.quantile(dif, 0.975))] if dif else None}
    disp = comp[f"disp{FOTO}"].astype(float)
    out["contratos_a_053"] = {"mediana": float(disp.median()) if n else None,
                              "p10": float(disp.quantile(0.10)) if n else None}
    return out


def run(mirada: str, registro: Path = REGISTRO, libro_dir: Path = LIBRO, salida: Path = SALIDA,
        hoy: pd.Timestamp | None = None, n_boot: int = N_BOOT, log=print) -> dict:
    if mirada not in MIRADAS:
        raise SystemExit(f"Estudio 56: mirada «{mirada}» desconocida (enero o abril).")
    fin, alfa = MIRADAS[mirada]
    hoy = hoy or pd.Timestamp.now(tz="UTC")
    if hoy < fin:
        raise SystemExit(f"Estudio 56: la mirada de {mirada} se evalúa desde el {fin:%Y-%m-%d}; no antes.")
    salida = Path(salida)
    if (salida / f"{mirada}.json").exists():
        raise SystemExit(f"Estudio 56: la mirada de {mirada} ya se evaluó ({salida / f'{mirada}.json'}).")
    if mirada == "abril":
        previa = salida / "enero.json"
        if not previa.exists():
            raise SystemExit("Estudio 56: primero va la mirada de enero.")
        if json.loads(previa.read_text(encoding="utf-8")).get("pasa"):
            raise SystemExit("Estudio 56: ya pasó en enero; no hay mirada de abril.")
    falta = dias_faltantes(registro, fin)
    if falta:  # evaluación única: no gastarla con días sin registrar (ítem 54)
        raise SystemExit(f"Estudio 56: faltan {len(falta)} días en el registro ({', '.join(falta[:6])}…); "
                         "esperar a que el registro diario los complete. No se evaluó nada.")
    rep = evaluar(cargar_senales(registro, fin), cargar_libro(libro_dir), alfa, n_boot)
    n = rep.get("principal", {}).get("operaciones", 0)
    if rep.get("pasa"):
        rep["veredicto"] = "PASA"
    elif mirada == "enero":
        rep["veredicto"] = "sigue hasta abril"
    else:
        rep["veredicto"] = "SIN CONCLUSIÓN (menos de 500 operaciones)" if n < MIN_OPS else "NO PASA"
    rep.update({"estudio": "Estudio 56 — señales de OKX al precio real del libro", "mirada": mirada,
                "ventanas": [str(INICIO.date()), str((fin - pd.Timedelta(days=1)).date())], "git_sha": git_sha()})
    salida.mkdir(parents=True, exist_ok=True)
    (salida / f"{mirada}.json").write_text(json.dumps(jsonable(rep), indent=2, ensure_ascii=False) + "\n",
                                           encoding="utf-8")
    log(f"Estudio 56 ({mirada}): {rep['veredicto']} | {rep.get('principal', {}).get('criterios')}")
    return rep
