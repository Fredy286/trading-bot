"""Estudio 59 (pre-registro 4760414, docs/01): ¿el mercado ya sabía lo que sabe nuestro modelo?

Une las predicciones fuera de muestra del Estudio 54 (contratos de 5 min, ETH y BTC) con el libro segundo a segundo de los
mismos contratos en Polymarket (conjunto público kachoio, CC0; `data/raw/polymarket_5m/`). El conjunto no trae ticks
antes del inicio de cada ventana, así que, según el pre-registro, el precio de referencia es el primer tick entre el
inicio y 5 s después (favorece al mercado, que ya vio 10 s más que el modelo).

Ganancia por acción = 1 si el lado de la señal gana − precio de venta de ese lado en Polymarket (sin comisión).
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from .experiment import git_sha, jsonable

DATOS = Path("data/raw/polymarket_5m")
PRED = Path("results/estudio54/predicciones.parquet")
MONEDAS = {"BTCUSDT": "btc", "ETHUSDT": "eth"}
COSTO_OKX = 0.52 + 0.045 * 0.52 * 0.48  # regla de señal del Estudio 55
MARGEN = 0.02
MIN_OPS = 500
ALFA = 0.05
N_BOOT = 10_000
SEMILLA = 59
TRAMO_S = 5  # el precio de referencia es el primer tick en [x, x + 5 s]
DESPUES_S = (10, 30, 60)  # informativo: comprar más tarde


def precios(ticks: pd.DataFrame, markets: pd.DataFrame, offset_s: int) -> pd.DataFrame:
    """Primer tick de cada mercado entre inicio + offset y inicio + offset + 5 s: compra/venta de «Up» y «Down»."""
    st = pd.to_datetime(markets["market_start"], utc=True).dt.as_unit("ns")  # segundos sin depender de la resolución
    ini = pd.Series((st.astype("int64") // 10**9).to_numpy(), index=markets["condition_id"].to_numpy())
    t = ticks.join(ini.rename("ini"), on="condition_id")
    t = t[(t["t"] >= t["ini"] + offset_s) & (t["t"] <= t["ini"] + offset_s + TRAMO_S)]
    t = t.sort_values(["condition_id", "t"]).drop_duplicates("condition_id")
    return t.set_index("condition_id")[["bu", "au", "bd", "ad"]]


def cargar(moneda: str, datos: Path = DATOS, pred: Path = PRED) -> pd.DataFrame:
    """Una fila por ventana con predicción del Estudio 54, resultado de Polymarket y precios en 0/10/30/60 s."""
    sym = {v: k for k, v in MONEDAS.items()}[moneda]
    m = pd.read_parquet(Path(datos) / f"{moneda}_markets.parquet")
    m = m[m["outcome"].isin(["Up", "Down"])].drop_duplicates("market_start")
    ticks = pd.read_parquet(Path(datos) / f"{moneda}_ticks.parquet", columns=["condition_id", "t", "bu", "au", "bd", "ad"])
    p = pd.read_parquet(pred)
    p = p[(p["simbolo"] == sym) & (p["dur"] == 5)].dropna(subset=["p"])
    p = p.assign(ventana=p.index + pd.Timedelta(minutes=1)).set_index("ventana")
    df = m.assign(ventana=pd.to_datetime(m["market_start"], utc=True)).set_index("ventana").join(
        p[["p", "y"]], how="inner")
    for off in (0, *DESPUES_S):
        pr = precios(ticks, m, off).add_suffix(f"_{off}")
        df = df.join(pr, on="condition_id")
    df["moneda"] = sym
    df["sube"] = (df["outcome"] == "Up").astype(float)
    return df


def _boot_dias(x: np.ndarray, dias: np.ndarray, n_boot: int, seed: int) -> np.ndarray:
    ds, inv = np.unique(dias, return_inverse=True)
    sumas = np.bincount(inv, weights=x, minlength=len(ds))
    cuentas = np.bincount(inv, minlength=len(ds)).astype(float)
    idx = np.random.default_rng(seed).integers(0, len(ds), size=(n_boot, len(ds)))
    return sumas[idx].sum(axis=1) / np.maximum(cuentas[idx].sum(axis=1), 1)


def _logit(x):
    x = np.clip(np.asarray(x, float), 1e-4, 1 - 1e-4)
    return np.log(x / (1 - x))


def _logistica(X: np.ndarray, y: np.ndarray, iters: int = 50) -> np.ndarray:
    """Regresión logística por Newton (con constante)."""
    A = np.column_stack([np.ones(len(X)), X])
    b = np.zeros(A.shape[1])
    for _ in range(iters):
        p = 1 / (1 + np.exp(-A @ b))
        W = p * (1 - p)
        H = A.T @ (A * W[:, None]) + 1e-9 * np.eye(A.shape[1])
        step = np.linalg.solve(H, A.T @ (y - p))
        b += step
        if np.abs(step).max() < 1e-10:
            break
    return b


def senales(df: pd.DataFrame, off: int = 0) -> pd.DataFrame:
    """Señales (regla del Estudio 55) con el precio de venta de su lado en Polymarket a inicio + off."""
    lado = np.where(df["p"] >= 0.5, 1, -1)
    pdir = np.where(lado == 1, df["p"], 1 - df["p"])
    s = df.assign(lado=lado, pdir=pdir)
    s = s[s["pdir"] - COSTO_OKX >= MARGEN].copy()
    s["precio"] = np.where(s["lado"] == 1, s[f"au_{off}"], s[f"ad_{off}"])
    s = s[(s["precio"] > 0) & (s["precio"] < 1)]
    s["gana"] = np.where(s["lado"] == 1, s["sube"], 1 - s["sube"])
    s["ganancia"] = s["gana"] - s["precio"]
    return s


def _resumen(s: pd.DataFrame) -> dict:
    if s.empty:
        return {"operaciones": 0}
    return {"operaciones": int(len(s)), "acierto": float(s["gana"].mean()), "precio_medio": float(s["precio"].mean()),
            "ganancia_media": float(s["ganancia"].mean()), "p_modelo_media": float(s["pdir"].mean())}


def evaluar(df: pd.DataFrame, n_boot: int = N_BOOT, seed: int = SEMILLA) -> dict:
    s = senales(df, 0)
    g = s["ganancia"].to_numpy(float)
    n = len(g)
    out = {"ventanas_unidas": int(len(df)), "principal": _resumen(s)}
    if n >= 2 and g.std(ddof=1) > 0:
        z = g.mean() / (g.std(ddof=1) / math.sqrt(n))
        p_valor = 0.5 * math.erfc(z / math.sqrt(2))
        lim = float(np.quantile(_boot_dias(g, s.index.floor("D").asi8, n_boot, seed), ALFA))
    else:
        p_valor, lim = float("nan"), float("nan")
    crit = {"min_500": n >= MIN_OPS, "p_menor_005": bool(p_valor < ALFA), "limite_mayor_0": bool(lim > 0)}
    out["principal"].update({"p_valor": p_valor, "limite_inferior_5": lim, "criterios": crit})
    out["pasa"] = all(crit.values())

    # informativo (pre-registrado)
    mid = (df["bu_0"] + df["au_0"]) / 2
    ok = mid.notna()
    out["correlacion_rangos_p_vs_mercado"] = {
        "todas": float(pd.Series(df.loc[ok, "p"]).rank().corr(mid[ok].rank())),
        "senales": float(s["p"].rank().corr(((s["bu_0"] + s["au_0"]) / 2).rank())) if len(s) > 2 else None}
    d = df[ok]
    X = np.column_stack([_logit(mid[ok]), _logit(d["p"])])
    y = d["sube"].to_numpy(float)
    b = _logistica(X, y)
    dias = d.index.floor("D").asi8
    ds, inv = np.unique(dias, return_inverse=True)
    rng = np.random.default_rng(seed + 1)
    coefs = []
    for _ in range(min(n_boot, 1000)):
        pick = rng.integers(0, len(ds), size=len(ds))
        rows = np.concatenate([np.flatnonzero(inv == k) for k in pick])
        coefs.append(_logistica(X[rows], y[rows])[2])
    out["logistica"] = {"coef_mercado": float(b[1]), "coef_modelo": float(b[2]),
                        "ic95_coef_modelo": [float(np.quantile(coefs, 0.025)), float(np.quantile(coefs, 0.975))]}
    out["mas_tarde"] = {f"+{o}s": _resumen(senales(df, o)) for o in DESPUES_S}
    out["por_moneda"] = {m: _resumen(s[s["moneda"] == m]) for m in MONEDAS}
    out["coincidencia_polymarket_okx"] = float(((df["sube"] * 2 - 1) == df["y"]).mean())
    return out


def run(datos: Path = DATOS, pred: Path = PRED, out_dir: Path = Path("results/estudio59"), n_boot: int = N_BOOT,
        log=print) -> dict:
    df = pd.concat([cargar(m, datos, pred) for m in MONEDAS.values()]).sort_index()
    rep = evaluar(df, n_boot)
    rep.update({"estudio": "Estudio 59 — ¿Polymarket ya cobraba la información del modelo? (pre-registro 4760414)",
                "precio_de_referencia": "primer tick entre el inicio y 5 s después (el conjunto no trae ticks previos)",
                "periodo": [str(df.index.min()), str(df.index.max())], "git_sha": git_sha()})
    pr = rep["principal"]
    log(f"H59: pasa={rep['pasa']} | {pr.get('operaciones')} señales, acierto {pr.get('acierto')}, "
        f"precio medio {pr.get('precio_medio')}, ganancia {pr.get('ganancia_media')}, p={pr.get('p_valor')}")
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "resultado.json").write_text(json.dumps(jsonable(rep), indent=2, ensure_ascii=False) + "\n",
                                            encoding="utf-8")
    return rep
