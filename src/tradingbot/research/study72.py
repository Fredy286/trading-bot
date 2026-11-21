"""Estudio 72 (pre-registro defc48c, docs/01): capa de vetos D1 y D2.

- D1: no operar una señal que va a favor de la tendencia de 60 min (tend60 = signo(ln C[t−1] − ln C[t−61]), cierres
  de 1 min del contado de Binance).
- D2: no operar si el contrato empieza (T0 = t + 1 min) de lunes a viernes entre las 9:30 y las 10:59 de Nueva York.

H72a: blitz con el p42 congelado (registro `blitz`), solo velas en horario abierto de IQ Option. H72b: gran bot de
OKX 15 min (registro `gran15`). En cada una, la suma de la ganancia de las señales vetadas debe ser < 0. Tres
miradas, cada una UNA sola vez (enero α 0,01; abril α 0,02; julio α 0,02), con Holm entre las hipótesis pendientes.
`desarrollo()` reproduce las cifras *post hoc* del pre-registro.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import study64
from .experiment import git_sha, jsonable
from .study63 import COSTO, _boot_semanas
from ..live import horario_iq

REG_BLITZ = Path("results/registro/blitz")
REG_15 = Path("results/registro/gran15")
SALIDA = Path("results/estudio72")
CACHE = Path("data/processed/estudio72")
INICIO = pd.Timestamp("2026-10-26", tz="UTC")
MIRADAS = {"enero": (pd.Timestamp("2027-01-19", tz="UTC"), 0.01),
           "abril": (pd.Timestamp("2027-04-27", tz="UTC"), 0.02),
           "julio": (pd.Timestamp("2027-07-27", tz="UTC"), 0.02)}
ORDEN = ("enero", "abril", "julio")
HIPOTESIS = ("H72a", "H72b")
MIN_VETADAS = 100
N_BOOT = 10_000
SEMILLA = 72
PAGO_BLITZ = 0.86
MIN = pd.Timedelta(minutes=1)


# ------------------------------------------------------------------------------------------------ reglas congeladas
def tendencia60(cierres: pd.Series, velas) -> np.ndarray:
    """signo(ln C[t−1] − ln C[t−61]); `cierres` indexado por el inicio de cada vela de 1 min. NaN si falta alguno."""
    velas = pd.DatetimeIndex(velas)
    a = cierres.reindex(velas - MIN).to_numpy(float)
    b = cierres.reindex(velas - 61 * MIN).to_numpy(float)
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.sign(np.log(a) - np.log(b))


def apertura_ny(t0) -> np.ndarray:
    """True si T0 cae de lunes a viernes entre las 9:30 y las 10:59 de Nueva York (con horario de verano)."""
    ny = pd.DatetimeIndex(t0).tz_convert("America/New_York")
    m = ny.hour * 60 + ny.minute
    return np.asarray((ny.dayofweek < 5) & (m >= 9 * 60 + 30) & (m < 11 * 60), dtype=bool)


def vetos(velas, lado: np.ndarray, tend: np.ndarray) -> dict[str, np.ndarray]:
    """D1 (a favor de la tendencia de 60 min), D2 (apertura de Nueva York) y el veto = D1 o D2."""
    d1 = ~np.isnan(tend) & (tend != 0) & (np.asarray(lado) == tend)
    d2 = apertura_ny(pd.DatetimeIndex(velas) + MIN)
    return {"D1": d1, "D2": d2, "veto": d1 | d2}


# ------------------------------------------------------------------------------------------------------- datos
def cierres_binance(symbol: str, inicio: pd.Timestamp, fin: pd.Timestamp, cache: Path = CACHE) -> pd.Series:
    """Cierres de 1 min del contado de Binance (archivos diarios públicos) en [inicio, fin), con caché por moneda."""
    from ..live.anticipada import download_daily

    df = download_daily("1m", f"{inicio:%Y-%m-%d}", f"{fin:%Y-%m-%d}", Path(cache) / symbol, symbol=symbol)
    return df["c"].astype(float)


def _leer(registro: Path, campos: tuple[str, ...]) -> pd.DataFrame:
    rows = []
    for f in sorted(Path(registro).glob("*.jsonl")):
        for line in f.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                rows.append({k: r.get(k) for k in campos})
    return pd.DataFrame(rows, columns=list(campos))


def cargar_blitz(registro: Path = REG_BLITZ, fin: pd.Timestamp | None = None) -> pd.DataFrame:
    """Señales del blitz con p42 (H44a): una por vela, con resultado de 3 bolsas («gana», «pierde» o «empate»)."""
    df = _leer(registro, ("vela", "lado", "p", "resultado"))
    if df.empty:
        return df.set_index("vela")
    df["vela"] = pd.to_datetime(df["vela"], utc=True)
    fin = fin if fin is not None else MIRADAS["julio"][0]
    df = df[(df["vela"] >= INICIO) & (df["vela"] < fin) & df["resultado"].isin(["gana", "pierde", "empate"])]
    df = df.drop_duplicates("vela").sort_values("vela").set_index("vela")
    df["lado_n"] = np.where(df["lado"] == "CALL", 1, -1)
    df["g"] = df["resultado"].map({"gana": PAGO_BLITZ, "pierde": -1.0, "empate": 0.0}).astype(float)
    df["moneda"] = "BTCUSDT"
    return df


def cargar_gran15(registro: Path = REG_15, fin: pd.Timestamp | None = None) -> pd.DataFrame:
    """Señales del gran bot de OKX 15 min (senal_gran = true, resultado ±1), indexadas por la vela de decisión."""
    df = _leer(registro, ("ventana", "moneda", "instrumento", "p_gran", "senal_gran", "resultado"))
    if df.empty:
        return df.set_index("ventana")
    df["ventana"] = pd.to_datetime(df["ventana"], utc=True)
    fin = fin if fin is not None else MIRADAS["julio"][0]
    df = df[(df["ventana"] >= INICIO) & (df["ventana"] < fin) & df["resultado"].isin([1, -1])
            & df["senal_gran"].fillna(False).astype(bool)]
    df = df.drop_duplicates(["moneda", "instrumento"]).sort_values("ventana")
    df["vela"] = df["ventana"] - MIN
    p = df["p_gran"].to_numpy(float)
    df["lado_n"] = np.where(p >= 0.5, 1, -1)
    df["g"] = np.where(df["lado_n"].to_numpy() == np.sign(df["resultado"].to_numpy(float)), 1 - COSTO, -COSTO)
    return df.set_index("vela")


# ----------------------------------------------------------------------------------------------------- evaluación
def semanas(index) -> np.ndarray:
    iso = pd.DatetimeIndex(index).isocalendar()
    return (iso["year"].astype(int) * 100 + iso["week"].astype(int)).to_numpy()


def _resumen(mask: np.ndarray, g: np.ndarray) -> dict:
    n = int(mask.sum())
    if not n:
        return {"operaciones": 0}
    dec = mask & (g != 0)
    return {"operaciones": n, "acierto_sin_empates": float((g[dec] > 0).mean()) if dec.any() else None,
            "ev_por_operacion": float(g[mask].mean()), "ganancia_total": float(g[mask].sum())}


def evaluar_una(df: pd.DataFrame, tend: np.ndarray, n_boot: int = N_BOOT, seed: int = SEMILLA) -> dict:
    """`df` (índice = vela de decisión) con lado_n y g; `tend` = tendencia de 60 min de cada fila."""
    g = df["g"].to_numpy(float)
    v = vetos(df.index, df["lado_n"].to_numpy(), tend)
    veto = v["veto"]
    boot = _boot_semanas(np.where(veto, g, 0.0), semanas(df.index), n_boot, seed) if len(df) else np.zeros(1)
    todas = np.ones(len(df), bool)
    out = {"senales": _resumen(todas, g), "vetadas": _resumen(veto, g), "resto": _resumen(~veto, g),
           "suma_vetadas": float(g[veto].sum()), "p": float((boot >= 0).mean()),
           "n_vetadas": int(veto.sum()), "sin_tendencia": int(np.isnan(tend).sum()),
           "informativo": {"D1": _resumen(v["D1"], g), "D2": _resumen(v["D2"], g)}}
    usr = (df.index.hour >= 2) & (df.index.hour < 6)
    out["informativo"]["horario_usuario"] = {"vetadas": _resumen(veto & usr, g), "resto": _resumen(~veto & usr, g)}
    return out


def holm(ps: dict[str, float | None], alfa: float, m: int) -> dict[str, bool]:
    """Holm entre las hipótesis evaluables (p no nulo); m = número de hipótesis pendientes en la mirada."""
    pasa = {h: False for h in ps}
    k = 0
    for h, p in sorted(((h, p) for h, p in ps.items() if p is not None), key=lambda x: x[1]):
        if p < alfa / max(m - k, 1):
            pasa[h] = True
            k += 1
        else:
            break
    return pasa


def _previas(salida: Path, mirada: str) -> list[dict]:
    out = []
    for m in ORDEN[:ORDEN.index(mirada)]:
        f = Path(salida) / f"{m}.json"
        if not f.exists():
            raise SystemExit(f"Estudio 72: primero va la mirada de {m}.")
        out.append(json.loads(f.read_text(encoding="utf-8")))
    return out


def run(mirada: str, reg_blitz: Path = REG_BLITZ, reg_15: Path = REG_15, salida: Path = SALIDA,
        hoy: pd.Timestamp | None = None, n_boot: int = N_BOOT, cierres=None, horario: dict | None = None,
        log=print) -> dict:
    if mirada not in MIRADAS:
        raise SystemExit(f"Estudio 72: mirada «{mirada}» desconocida (enero, abril o julio).")
    fin, alfa = MIRADAS[mirada]
    hoy = hoy or pd.Timestamp.now(tz="UTC")
    if hoy < fin:
        raise SystemExit(f"Estudio 72: la mirada de {mirada} se evalúa desde el {fin:%Y-%m-%d}; no antes.")
    salida = Path(salida)
    if (salida / f"{mirada}.json").exists():
        raise SystemExit(f"Estudio 72: la mirada de {mirada} ya se evaluó.")
    ya = {h for r in _previas(salida, mirada) for h, x in r.get("hipotesis", {}).items() if x.get("pasa")}
    pendientes = [h for h in HIPOTESIS if h not in ya]
    if not pendientes:
        raise SystemExit("Estudio 72: las dos hipótesis ya pasaron; no hay más miradas.")
    for reg in (reg_blitz, reg_15):
        falta = study64.dias_faltantes(reg, fin)
        if falta:  # evaluación única: no gastarla con días sin registrar (ítem 54)
            raise SystemExit(f"Estudio 72: faltan {len(falta)} días en {reg} ({', '.join(falta[:6])}…). No se evaluó.")
    cierres = cierres or (lambda s: cierres_binance(s, INICIO - pd.Timedelta(days=2), fin))
    horario = horario if horario is not None else horario_iq.cargar()
    res: dict[str, dict] = {}
    if "H72a" in pendientes:
        b = cargar_blitz(reg_blitz, fin)
        b = b[horario_iq.abierto_vec(b.index, horario)] if len(b) else b
        res["H72a"] = evaluar_una(b, tendencia60(cierres("BTCUSDT"), b.index) if len(b) else np.zeros(0), n_boot)
        res["H72a"]["horario_iq"] = horario
    if "H72b" in pendientes:
        f = cargar_gran15(reg_15, fin)
        tend = np.full(len(f), np.nan)
        for s in ("BTCUSDT", "ETHUSDT"):
            m = (f["moneda"] == s).to_numpy() if len(f) else np.zeros(0, bool)
            if m.any():
                tend[m] = tendencia60(cierres(s), f.index[m])
        res["H72b"] = evaluar_una(f, tend, n_boot)
    ps = {h: (r["p"] if r["n_vetadas"] >= MIN_VETADAS else None) for h, r in res.items()}
    pasa = holm(ps, alfa, len(pendientes))
    for h, r in res.items():
        r["pasa"] = bool(pasa[h])
        r["veredicto"] = ("PASA" if r["pasa"] else
                          f"SIN CONCLUSIÓN (menos de {MIN_VETADAS} vetadas)" if ps[h] is None else
                          "sigue en la próxima mirada" if mirada != "julio" else "NO PASA")
    rep = {"estudio": "Estudio 72 — capa de vetos D1 y D2 (pre-registro defc48c)", "mirada": mirada, "alfa": alfa,
           "pendientes": pendientes, "ya_pasaron": sorted(ya), "hipotesis": res, "git_sha": git_sha(),
           "senales_periodo": [str(INICIO.date()), str((fin - pd.Timedelta(days=1)).date())],
           "consecuencia": "veto en la práctica del blitz si pasan H72a, H44a y H44a-ab; en OKX 15 min si pasan H72b y H69"}
    salida.mkdir(parents=True, exist_ok=True)
    (salida / f"{mirada}.json").write_text(json.dumps(jsonable(rep), indent=2, ensure_ascii=False) + "\n",
                                           encoding="utf-8")
    log(f"Estudio 72 ({mirada}): " + " | ".join(f"{h}: {r['veredicto']} (vetadas {r['n_vetadas']}, "
                                                  f"suma {r['suma_vetadas']:+.1f}, p {r['p']:.4f})" for h, r in res.items()))
    return rep


# ------------------------------------------------------------------------------------------------- desarrollo
def _cierres_desarrollo(symbol: str) -> pd.Series:
    """Cierres locales de Binance 2024-05 → 2026-10 (estudio3 + bolsas_usdt), solo para reproducir el pre-registro."""
    from . import bolsas, study3, study42

    sp = study3.load(Path("data/raw/estudio3"), symbol, "spot")["c"]
    sp = sp[sp.index >= pd.Timestamp("2024-05-01", tz="UTC")]
    meses = ("2026-09", "2026-10")
    extra = pd.concat([study42.month_closes("binance", m) if symbol == "BTCUSDT" else
                       bolsas.month_closes(symbol, "binance", m) for m in meses])
    x = pd.concat([sp, extra]).sort_index()
    return x[~x.index.duplicated(keep="first")].astype(float)


def desarrollo(n_boot: int = N_BOOT) -> dict:
    """Cifras post hoc del pre-registro (control: H72a 1 722 vetadas y −133,6; H72b 3 273 vetadas y −58,7)."""
    from . import apilado, study63 as s63, study66 as s66, study67 as s67

    c = {s: _cierres_desarrollo(s) for s in ("BTCUSDT", "ETHUSDT")}
    t = s66.tabla()
    t = t[t.index >= pd.Timestamp("2025-11-01", tz="UTC")]
    toma, g = s66.politica(t["propia"].to_numpy(), t["q"].to_numpy(), t["y"].to_numpy())
    b = pd.DataFrame({"lado_n": np.where(t["propia"].to_numpy() >= 0.5, 1, -1), "g": g}, index=t.index)[toma]
    b = b[horario_iq.abierto_vec(b.index, horario_iq.PRUDENTE)]
    out = {"H72a": evaluar_una(b, tendencia60(c["BTCUSDT"], b.index), n_boot)}
    p54 = pd.read_parquet(s63.P54)
    otras = {k: pd.read_parquet(f)["p"] for k, f in s63.FUENTES.items()}
    partes = []
    for s in s63.MONEDAS:
        df = s67.tabla(s, p54, otras)
        gran, _ = apilado.walk_forward(df, s67.OPINIONES)
        x = df.assign(gran=gran).dropna(subset=["gran"])
        tk, gk = s63.politica(x["gran"].to_numpy(), x["y"].to_numpy())
        f = pd.DataFrame({"lado_n": np.where(x["gran"].to_numpy() >= 0.5, 1, -1), "g": gk, "moneda": s},
                         index=x.index)[tk]
        f["tend"] = tendencia60(c[s], f.index)
        partes.append(f)
    f = pd.concat(partes).sort_index()
    out["H72b"] = evaluar_una(f, f["tend"].to_numpy(), n_boot)
    return out
