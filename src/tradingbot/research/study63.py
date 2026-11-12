"""Estudio 63 (pre-registro 841c4ce, docs/01): el «gran bot». Un metamodelo combina seis opiniones propias (todas
predicciones fuera de muestra, calculadas con información hasta el segundo 49 de la vela de decisión) para los contratos
de 5 min de OKX, y se compara con la opinión propia sola (lo que hoy usa el bot).

Opiniones: Estudio 54 (5 min, la moneda y la otra), Estudio 20 (BTC 1 min, Binance), Estudios 42, 51 y 53 (BTC, ETH y
SOL a 3 min con el compuesto). Metamodelo: regresión logística con constante, sin penalización, una por moneda,
entrenada mes a mes solo con el pasado (desde el 2025-09-01 hasta 10 min antes del mes de prueba).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from .experiment import git_sha, jsonable

FUENTES = {"p20": Path("results/estudio20/predicciones.parquet"), "p42": Path("results/estudio42/predicciones.parquet"),
           "p51": Path("results/estudio51/predicciones.parquet"), "p53": Path("results/estudio53/predicciones.parquet")}
P54 = Path("results/estudio54/predicciones.parquet")
MONEDAS = ("ETHUSDT", "BTCUSDT")
OPINIONES = ("propia", "otra", "p20", "p42", "p51", "p53")
INICIO = pd.Timestamp("2025-09-01", tz="UTC")
PRUEBA = [str(p) for p in pd.period_range("2025-11", "2026-10", freq="M")]
FIN = pd.Timestamp("2026-10-26", tz="UTC")
COSTO = 0.52 + 0.045 * 0.52 * 0.48  # 0,5312
MARGEN = 0.02
PURGA = pd.Timedelta(minutes=10)
N_BOOT = 10_000
SEMILLA = 63


def logit(p) -> np.ndarray:
    p = np.clip(np.asarray(p, float), 0.01, 0.99)
    return np.log(p / (1 - p))


def logistica(X: np.ndarray, y: np.ndarray, iters: int = 100) -> np.ndarray:
    """Regresión logística por Newton (constante + coeficientes), sin penalización."""
    A = np.column_stack([np.ones(len(X)), X])
    b = np.zeros(A.shape[1])
    for _ in range(iters):
        p = 1 / (1 + np.exp(-np.clip(A @ b, -30, 30)))
        H = A.T @ (A * (p * (1 - p))[:, None]) + 1e-9 * np.eye(A.shape[1])
        paso = np.linalg.solve(H, A.T @ (y - p))
        b += paso
        if np.abs(paso).max() < 1e-10:
            break
    return b


def predecir(b: np.ndarray, X: np.ndarray) -> np.ndarray:
    return 1 / (1 + np.exp(-np.clip(b[0] + X @ b[1:], -30, 30)))


def tabla(moneda: str, p54: pd.DataFrame, otras: dict[str, pd.Series]) -> pd.DataFrame:
    """Una fila por minuto de decisión de 5 min de la moneda, con las seis opiniones y la etiqueta (±1)."""
    otra = [m for m in MONEDAS if m != moneda][0]
    mia = p54[(p54["simbolo"] == moneda) & (p54["dur"] == 5)]
    df = pd.DataFrame({"propia": mia["p"], "y": mia["y"]}, index=mia.index)
    o = p54[(p54["simbolo"] == otra) & (p54["dur"] == 5)]["p"]
    df["otra"] = o.reindex(df.index)
    for k, s in otras.items():
        df[k] = s.reindex(df.index)
    df = df[(df.index >= INICIO) & (df.index < FIN)].dropna(subset=[*OPINIONES, "y"])
    df["moneda"] = moneda
    return df


def walk_forward(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Probabilidad del metamodelo para cada fila de los meses de prueba, entrenando solo con el pasado."""
    mes = np.asarray(df.index.tz_convert(None).to_period("M").astype(str))
    X, y = logit(df[list(OPINIONES)].to_numpy()), (df["y"].to_numpy() > 0).astype(float)
    out = pd.Series(np.nan, index=df.index)
    coefs = {}
    for m in PRUEBA:
        ini = pd.Timestamp(m + "-01", tz="UTC")
        train = np.asarray(df.index < ini - PURGA)
        test = mes == m
        if train.sum() < 1000 or not test.any():
            continue
        b = logistica(X[train], y[train])
        out[test] = predecir(b, X[test])
        coefs[m] = dict(zip(("constante", *OPINIONES), (float(x) for x in b)))
    return df.assign(gran=out).dropna(subset=["gran"]), coefs


def politica(p: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """(se opera, ganancia por acción) con la regla del Estudio 55."""
    lado = np.where(p >= 0.5, 1, -1)
    pdir = np.where(lado == 1, p, 1 - p)
    toma = pdir - COSTO >= MARGEN - 1e-12
    gana = lado == np.sign(y)
    return toma, np.where(toma, np.where(gana, 1 - COSTO, -COSTO), 0.0)


def _resumen(toma: np.ndarray, g: np.ndarray, t: pd.DatetimeIndex) -> dict:
    n = int(toma.sum())
    dias = max((t.max() - t.min()).days + 1, 1) if len(t) else 1
    if not n:
        return {"operaciones": 0}
    return {"operaciones": n, "por_dia": n / dias, "acierto": float((g[toma] > 0).mean()),
            "ev_por_operacion": float(g[toma].mean()), "ganancia_total": float(g.sum())}


def _logloss(p: np.ndarray, y: np.ndarray) -> np.ndarray:
    p = np.clip(p, 1e-6, 1 - 1e-6)
    yb = (y > 0).astype(float)
    return -(yb * np.log(p) + (1 - yb) * np.log(1 - p))


def _boot_semanas(a: np.ndarray, semanas: np.ndarray, n_boot: int, seed: int) -> np.ndarray:
    """Sumas de `a` remuestreando semanas ISO completas con reemplazo."""
    ws, inv = np.unique(semanas, return_inverse=True)
    sumas = np.bincount(inv, weights=a, minlength=len(ws))
    idx = np.random.default_rng(seed).integers(0, len(ws), size=(n_boot, len(ws)))
    return sumas[idx].sum(axis=1)


def evaluar(res: pd.DataFrame, n_boot: int = N_BOOT, seed: int = SEMILLA) -> dict:
    y = res["y"].to_numpy()
    tb, gb = politica(res["propia"].to_numpy(), y)
    tg, gg = politica(res["gran"].to_numpy(), y)
    iso = res.index.isocalendar()
    semanas = (iso["year"].astype(int) * 100 + iso["week"].astype(int)).to_numpy()
    d = _boot_semanas(gg - gb, semanas, n_boot, seed)
    dg = float(gg.sum() - gb.sum())
    lim = float(np.quantile(d, 0.05))
    crit = {"limite_5_mayor_0": lim > 0, "min_300": int(tg.sum()) >= 300}
    ll_b, ll_g = _logloss(res["propia"].to_numpy(), y), _logloss(res["gran"].to_numpy(), y)
    n = len(res)
    dl = _boot_semanas(ll_g - ll_b, semanas, min(n_boot, 2000), seed + 1) / n
    out = {"filas": n, "principal": {"delta_ganancia": dg, "limite_inferior_5": lim,
                                     "p_bootstrap": float((d <= 0).mean()), "criterios": crit},
           "pasa": all(crit.values()),
           "base": _resumen(tb, gb, res.index), "gran_bot": _resumen(tg, gg, res.index),
           "logloss": {"base": float(ll_b.mean()), "gran_bot": float(ll_g.mean()), "delta": float((ll_g - ll_b).mean()),
                       "ic95_delta": [float(np.quantile(dl, 0.025)), float(np.quantile(dl, 0.975))]}}
    out["por_moneda"] = {}
    for m in MONEDAS:
        s = (res["moneda"] == m).to_numpy()
        out["por_moneda"][m] = {"base": _resumen(tb[s], gb[s], res.index[s]),
                                "gran_bot": _resumen(tg[s], gg[s], res.index[s]),
                                "delta_ganancia": float(gg[s].sum() - gb[s].sum())}
    # informativo: «acuerdo» (la base solo cuando la otra moneda apunta igual), umbrales y horario del usuario
    acuerdo = tb & (np.sign(res["propia"].to_numpy() - 0.5) == np.sign(res["otra"].to_numpy() - 0.5))
    out["acuerdo"] = _resumen(acuerdo, np.where(acuerdo, gb, 0.0), res.index)
    pg = res["gran"].to_numpy()
    for u in (0.57, 0.60):
        tu = tg & (np.maximum(pg, 1 - pg) >= u)
        out[f"gran_bot_p{round(u * 100)}"] = _resumen(tu, np.where(tu, gg, 0.0), res.index)
    usr = (res.index.hour >= 2) & (res.index.hour < 6)
    out["horario_usuario"] = {"base": _resumen(tb & usr, np.where(usr, gb, 0.0), res.index),
                              "gran_bot": _resumen(tg & usr, np.where(usr, gg, 0.0), res.index)}
    return out


def run(out_dir: Path = Path("results/estudio63"), n_boot: int = N_BOOT, log=print) -> dict:
    p54 = pd.read_parquet(P54)
    otras = {k: pd.read_parquet(f)["p"] for k, f in FUENTES.items()}
    partes, coefs = [], {}
    for m in MONEDAS:
        r, c = walk_forward(tabla(m, p54, otras))
        partes.append(r)
        coefs[m] = c
    res = pd.concat(partes).sort_index()
    rep = evaluar(res, n_boot)
    rep.update({"estudio": "Estudio 63 — el «gran bot» para OKX 5 min (pre-registro 841c4ce)", "coeficientes": coefs,
                "meses_prueba": [PRUEBA[0], PRUEBA[-1]], "git_sha": git_sha()})
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "resultado.json").write_text(json.dumps(jsonable(rep), indent=2, ensure_ascii=False) + "\n",
                                            encoding="utf-8")
    res[["moneda", "y", "propia", "gran"]].to_parquet(out_dir / "predicciones.parquet")
    pr = rep["principal"]
    log(f"H63: pasa={rep['pasa']} | ΔG={pr['delta_ganancia']:+.2f} (lím. 5 % {pr['limite_inferior_5']:+.2f}) | "
        f"base {rep['base']} | gran bot {rep['gran_bot']}")
    return rep
