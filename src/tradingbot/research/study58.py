"""Estudio 58 (pre-registro en docs/01, 2026-11-10): ¿las señales registradas de BTC (H16b) que entran en una marca
de 5 min (:00, :05…) aciertan menos que las demás? Observación *post hoc* del Estudio 57, probada con datos nuevos.

Se evalúa UNA sola vez, después del sello del registro (2027-01-19). Antes de esa fecha, o si falta algún día de la
ventana, `run` se niega a leer los resultados (las pruebas pasan `hoy` y datos sintéticos).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from ..live.registro import SELLO
from .experiment import git_sha, jsonable
from .study49 import END, END_MAX, START, _last_contiguous_end, load_signals, missing_days

PAYOUT = 0.85
ALPHA = 0.05
MIN_M5 = 500
N_BOOT = 10_000
SEED = 12345


def entry_m5(velas: pd.Series | pd.DatetimeIndex) -> np.ndarray:
    """La entrada de la vela t es t + 60 s (segundo 50 + clic a +10 s): M5 si ese minuto es múltiplo de 5."""
    t = pd.DatetimeIndex(velas) + pd.Timedelta(minutes=1)
    return (t.minute.to_numpy() % 5) == 0


def entry_quarter(velas: pd.Series | pd.DatetimeIndex) -> np.ndarray:
    t = pd.DatetimeIndex(velas) + pd.Timedelta(minutes=1)
    return (t.minute.to_numpy() % 15) == 0


def _stats(res: np.ndarray) -> dict:
    nz = res[res != 0]
    n = int(len(nz))
    pnl = np.where(res == 0, 0.0, np.where(res > 0, PAYOUT, -1.0))
    return {"operaciones": int(len(res)), "sin_empate": n, "aciertos": int((nz > 0).sum()),
            "acierto": float((nz > 0).mean()) if n else None, "ev": float(pnl.mean()) if len(res) else None,
            "ganancia_total": float(pnl.sum())}


def diff_test(res: np.ndarray, m5: np.ndarray, days: np.ndarray, n_boot: int = N_BOOT, seed: int = SEED) -> dict:
    """D = acierto(O) − acierto(M5), sin empates; bootstrap de días completos."""
    keep = res != 0
    win, m, dd = (res[keep] > 0).astype(float), m5[keep], days[keep]
    uniq, inv = np.unique(dd, return_inverse=True)
    k = len(uniq)
    # sumas por día: aciertos y conteos en M5 y en O
    wm = np.bincount(inv, weights=win * m, minlength=k)
    nm = np.bincount(inv, weights=m.astype(float), minlength=k)
    wo = np.bincount(inv, weights=win * ~m, minlength=k)
    no = np.bincount(inv, weights=(~m).astype(float), minlength=k)

    def d_of(w):
        a, b, c, e = w @ wo, w @ no, w @ wm, w @ nm
        return (a / b - c / e) if b > 0 and e > 0 else np.nan

    ones = np.ones(k)
    d = d_of(ones)
    rng = np.random.default_rng(seed)
    boots = np.array([d_of(np.bincount(rng.integers(0, k, k), minlength=k).astype(float)) for _ in range(n_boot)])
    boots = boots[~np.isnan(boots)]
    p = (int((boots <= 0).sum()) + 1) / (len(boots) + 1)
    lo, hi = np.percentile(boots, [2.5, 97.5]) if len(boots) else (np.nan, np.nan)
    return {"D": float(d), "ic95": [float(lo), float(hi)], "p_unilateral": float(p), "dias": int(k),
            "m5_sin_empate": int(m.sum()), "o_sin_empate": int((~m).sum())}


def evaluate(df: pd.DataFrame, n_boot: int = N_BOOT) -> dict:
    velas = pd.DatetimeIndex(df["vela"])
    res = df["res"].to_numpy()
    m5 = entry_m5(velas)
    days = velas.strftime("%Y-%m-%d").to_numpy()
    t = diff_test(res, m5, days, n_boot)
    todas, solo_o, solo_m5 = _stats(res), _stats(res[~m5]), _stats(res[m5])
    crit = {"p": t["p_unilateral"] < ALPHA,
            "ev": solo_o["ev"] is not None and todas["ev"] is not None and solo_o["ev"] > todas["ev"],
            "min_500": t["m5_sin_empate"] >= MIN_M5}
    info = {}
    hi = df["p"].to_numpy() >= 0.60
    if hi.sum() and (res[hi] != 0).sum():
        info["p060"] = {"todas": _stats(res[hi]), "solo_o": _stats(res[hi & ~m5]), "solo_m5": _stats(res[hi & m5]),
                        "prueba": diff_test(res[hi], m5[hi], days[hi], min(n_boot, 2000))}
    q = entry_quarter(velas)
    info["cuartos_frente_a_otras_m5"] = {"cuartos": _stats(res[q]), "otras_m5": _stats(res[m5 & ~q])}
    weeks = velas.strftime("%G-%V").to_numpy()
    serie = {}
    for w in np.unique(weeks):
        s = weeks == w
        a, b = _stats(res[s & ~m5])["acierto"], _stats(res[s & m5])["acierto"]
        serie[str(w)] = None if a is None or b is None else a - b
    info["D_semanal"] = serie
    return {"senales": int(len(df)), "H58": {**t, "todas": todas, "solo_o": solo_o, "solo_m5": solo_m5,
                                              "criterios": crit, "pasa": all(crit.values())},
            "informativo": info}


def run(reg_dir: Path = Path("results/registro/btc"), out_dir: Path = Path("results/estudio58"),
        hoy: pd.Timestamp | None = None, n_boot: int = N_BOOT, log=print, exigir_completo: bool = True) -> dict:
    hoy = hoy or pd.Timestamp.now(tz="UTC")
    if hoy < SELLO:
        raise SystemExit(f"Estudio 58: el registro está sellado hasta {SELLO:%Y-%m-%d}; no se evalúa antes.")
    falta = missing_days(reg_dir, END) if exigir_completo else []
    if falta:
        raise SystemExit(f"Estudio 58: faltan {len(falta)} días en el registro ({', '.join(falta[:10])}…); "
                         "esperar a que el registro diario los complete. No se evaluó nada.")
    tope = _last_contiguous_end(reg_dir) if exigir_completo else END_MAX
    end = END
    while True:
        rep = evaluate(load_signals(reg_dir, end), n_boot)
        short = not rep["H58"]["criterios"]["min_500"]
        if not short or end >= END_MAX or end >= hoy.normalize() or end >= tope:
            break
        nuevo = min(end + pd.Timedelta(days=7), END_MAX, hoy.normalize(), max(tope, end))
        if nuevo <= end:
            break
        end = nuevo
    rep.update({"estudio": "Estudio 58 — entradas M5 de las señales registradas de BTC (H16b)", "git_sha": git_sha(),
                "ventana": [str(START.date()), str((end - pd.Timedelta(days=1)).date())]})
    if short:
        rep["H58"]["veredicto"] = "sin datos suficientes" if end >= END_MAX else "esperar (faltan operaciones)"
    log(f"H58: pasa={rep['H58']['pasa']} | D={rep['H58']['D']:+.4f} p={rep['H58']['p_unilateral']:.4f} | "
        f"{rep['H58']['criterios']}")
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "resultado.json").write_text(json.dumps(jsonable(rep), indent=2, ensure_ascii=False), encoding="utf-8")
    return rep
