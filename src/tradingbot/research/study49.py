"""Estudio 49 (pre-registro en docs/01, 2026-11-05): confirmación del filtro de «racha reciente» del Estudio 48 con las
señales ya registradas del modelo congelado de BTC (H16b, `results/registro/btc/*.jsonl`).

Se evalúa UNA sola vez, después del sello del registro (2027-01-19). Antes de esa fecha `run` se niega a leer los
resultados (salvo en las pruebas, que pasan `hoy`).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from ..live.registro import SELLO
from .experiment import git_sha, jsonable
from .study48 import evaluate_filter, persistence, streak_rates

PAYOUT = 0.85
BE = 1 / (1 + PAYOUT)
START = pd.Timestamp("2026-10-26", tz="UTC")
END = pd.Timestamp("2027-01-19", tz="UTC")  # velas hasta el 2027-01-18 23:59
END_MAX = pd.Timestamp("2027-04-26", tz="UTC")  # ampliación máxima si faltan operaciones
RESOLVED_AFTER = pd.Timedelta(minutes=3)  # vela ≤ t − 3 min → ya resuelta
MIN_OPS = 300
N_BOOT = 10_000
_MAP = {"gana": 1.0, "pierde": -1.0, "empate": 0.0}


def load_signals(reg_dir: Path, end: pd.Timestamp = END) -> pd.DataFrame:
    rows = []
    for f in sorted(Path(reg_dir).glob("*.jsonl")):
        for line in f.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
    df = pd.DataFrame(rows, columns=["vela", "resultado", "p", "umbral_060", "modelo"])
    if df.empty:
        return df
    df["vela"] = pd.to_datetime(df["vela"], utc=True)
    df = df[(df["vela"] >= START) & (df["vela"] < end) & df["resultado"].isin(list(_MAP))]
    df = df.drop_duplicates("vela").sort_values("vela").reset_index(drop=True)
    df["res"] = df["resultado"].map(_MAP).astype(float)
    return df


def missing_days(reg_dir: Path, end: pd.Timestamp = END) -> list[str]:
    """Días de la ventana [START, end) sin archivo `AAAA-MM-DD.jsonl` en el registro (el registro diario los reintenta)."""
    have = {f.stem for f in Path(reg_dir).glob("*.jsonl")}
    return [f"{d:%Y-%m-%d}" for d in pd.date_range(START, end, freq="D", inclusive="left") if f"{d:%Y-%m-%d}" not in have]


def _last_contiguous_end(reg_dir: Path) -> pd.Timestamp:
    """Fin (exclusivo) del tramo de días seguidos con archivo, empezando en START."""
    have = {f.stem for f in Path(reg_dir).glob("*.jsonl")}
    d = START
    while f"{d:%Y-%m-%d}" in have and d < END_MAX:
        d += pd.Timedelta(days=1)
    return d


def evaluate(df: pd.DataFrame, n_boot: int = N_BOOT) -> dict:
    times = pd.DatetimeIndex(df["vela"])
    res = df["res"].to_numpy()
    ra, rb = streak_rates(times, times + RESOLVED_AFTER, res)
    out = {"senales": len(df), "persistencia": persistence(res, times), "hipotesis": {}}
    for h, rate in (("H49a", ra), ("H49b", rb)):
        e = evaluate_filter(res, times, rate, BE, PAYOUT, n_boot)
        nt, ns = e["tomadas"].get("operaciones", 0), e["saltadas"].get("operaciones", 0)
        crit = {"diferencia_ic": e["diferencia_acierto"]["lo"] > 0,
                "ev": nt > 0 and e["tomadas"]["ev"] > e["base"].get("ev", float("nan")),
                "min_300": nt >= MIN_OPS and ns >= MIN_OPS}
        e["ganancia_total"] = {k: (e[k].get("ev", 0.0) * e[k].get("operaciones", 0)) for k in ("base", "tomadas")}
        # p ≥ 0,60 (informativo)
        hi = df["p"].to_numpy() >= 0.60
        e["informativo_p060"] = evaluate_filter(res[hi], times[hi], rate[hi], BE, PAYOUT, min(n_boot, 2000)) \
            if hi.sum() else None
        out["hipotesis"][h] = {**e, "criterios": crit, "pasa": all(crit.values())}
    return out


def run(reg_dir: Path = Path("results/registro/btc"), out_dir: Path = Path("results/estudio49"),
        hoy: pd.Timestamp | None = None, n_boot: int = N_BOOT, log=print, exigir_completo: bool = True) -> dict:
    hoy = hoy or pd.Timestamp.now(tz="UTC")
    if hoy < SELLO:
        raise SystemExit(f"Estudio 49: el registro está sellado hasta {SELLO:%Y-%m-%d}; no se evalúa antes.")
    # Evaluación única: no gastarla con días sin registrar (nota de procedimiento del 2026-11-07 en docs/01).
    falta = missing_days(reg_dir, END) if exigir_completo else []
    if falta:
        raise SystemExit(f"Estudio 49: faltan {len(falta)} días en el registro ({', '.join(falta[:10])}…); "
                         "esperar a que el registro diario los complete. No se evaluó nada.")
    tope = _last_contiguous_end(reg_dir) if exigir_completo else END_MAX
    end = END
    rep = None
    while True:
        rep = evaluate(load_signals(reg_dir, end), n_boot)
        short = not all(h["criterios"]["min_300"] for h in rep["hipotesis"].values())
        if not short or end >= END_MAX or end >= hoy.normalize() or end >= tope:
            break
        nuevo = min(end + pd.Timedelta(days=7), END_MAX, hoy.normalize(), max(tope, end))
        if nuevo <= end:
            break
        end = nuevo
    rep.update({"estudio": "Estudio 49 — confirmación del filtro de racha con señales registradas de H16b",
                "git_sha": git_sha(), "ventana": [str(START.date()), str((end - pd.Timedelta(days=1)).date())],
                "equilibrio": BE})
    if short:
        for h in rep["hipotesis"].values():
            h["veredicto"] = "sin datos suficientes" if end >= END_MAX else "esperar (faltan operaciones)"
    for h, r in rep["hipotesis"].items():
        log(f"{h}: pasa={r['pasa']} | {r['criterios']}")
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "resultado.json").write_text(json.dumps(jsonable(rep), indent=2, ensure_ascii=False), encoding="utf-8")
    return rep
