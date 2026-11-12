"""El «gran bot» (Estudios 63 y 64): un metamodelo congelado que combina seis opiniones de modelos congelados para los
contratos de 5 min de OKX (ETH y BTC).

Opiniones, todas con información hasta el segundo 49 de la vela de decisión:
- «propia» y «otra»: los modelos de OKX 5 min de la moneda y de la otra moneda (Estudio 55);
- «p20»: BTC 1 min con Binance (H16b, Estudio 16);
- «p42», «p51», «p53»: BTC, ETH y SOL a 3 min con el compuesto de Binance, Bybit y OKX (Estudios 44, 52 y 64).

`congelar()` ajusta UNA vez el metamodelo con todo el desarrollo del Estudio 63 (2025-09-01 → 2026-10-25).
`gran5_day()` calcula, para un día, las seis opiniones en cada minuto de decisión de 5 min, la probabilidad del gran bot,
la de la base (opinión propia) y el resultado (oficial de OKX si se tiene; si no, el reconstruido del Estudio 54). El
registro diario lo guarda en `results/registro/gran5/` (sellado hasta el 2027-01-19).
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from ..research import study63
from ..research.experiment import git_sha
from ..timeutil import utcnow

OPINIONES = study63.OPINIONES
MONEDAS = study63.MONEDAS
CONFIG = Path("config/gran_bot_okx5.json")
REGISTRO = ("Estudio 64 (pre-registro bda4760): metamodelo congelado del gran bot, ajustado una vez con todo el "
            "desarrollo del Estudio 63")
DENTRO = Path("results/okx_dentro")


def bases() -> dict[str, tuple[Path, Path]]:
    """Modelos congelados de cada opinión: (archivo del modelo, registro con su SHA-256)."""
    from .anticipada import MODEL_PATH, REG_PATH
    from .blitz import MODELOS as BLITZ
    from .okx_eventos import MODELOS as OKX

    return {"okx5_ETHUSDT": OKX["ETHUSDT"], "okx5_BTCUSDT": OKX["BTCUSDT"], "p20": (MODEL_PATH, REG_PATH),
            "p42": BLITZ["BTCUSDT"], "p51": BLITZ["ETHUSDT"], "p53": BLITZ["SOLUSDT"]}


def congelar(log=print, destino: Path | None = None) -> dict:
    destino = Path(destino or CONFIG)
    if destino.exists():
        raise FileExistsError(f"{destino} ya existe: el metamodelo se ajusta una sola vez (pre-registro).")
    p54 = pd.read_parquet(study63.P54)
    otras = {k: pd.read_parquet(f)["p"] for k, f in study63.FUENTES.items()}
    coef, filas = {}, {}
    for m in MONEDAS:
        df = study63.tabla(m, p54, otras)
        b = study63.logistica(study63.logit(df[list(OPINIONES)].to_numpy()), (df["y"].to_numpy() > 0).astype(float))
        coef[m] = dict(zip(("constante", *OPINIONES), (float(x) for x in b)))
        filas[m] = int(len(df))
    info = {}
    for k, (mp, rp) in bases().items():
        r = json.loads(Path(rp).read_text(encoding="utf-8"))
        info[k] = {"model_id": r["model_id"], "model_sha256": r["model_sha256"], "archivo": str(mp)}
    meta = {"coeficientes": coef, "opiniones": list(OPINIONES), "filas_ajuste": filas,
            "periodo_ajuste": ["2025-09-01", "2026-10-25"], "bases": info, "costo": study63.COSTO,
            "margen": study63.MARGEN, "git_sha": git_sha(), "creado": utcnow().isoformat(), "registro": REGISTRO}
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    log(f"Metamodelo congelado en {destino}: {coef}")
    return meta


def combinar(coef: dict, opiniones: dict[str, float]) -> float:
    """Probabilidad de «Al alza» del gran bot con los coeficientes congelados de una moneda."""
    z = coef["constante"] + sum(coef[k] * float(study63.logit(opiniones[k])) for k in OPINIONES)
    return 1 / (1 + math.exp(-max(min(z, 30.0), -30.0)))


def filas_dia(op: pd.DataFrame, coef: dict, resultados: dict[str, tuple[int, str]]) -> list[dict]:
    """Una fila por moneda y minuto de decisión de 5 min con las seis opiniones completas.

    `op`: índice = minuto de decisión t; columnas okx5_ETHUSDT, okx5_BTCUSDT, p20, p42, p51, p53 (probabilidad de subir).
    `resultados`: contrato → (+1 sube / −1 baja, fuente)."""
    from .okx_eventos import inst_id

    out = []
    grid = op[((op.index.minute + 1) % 5) == 0].dropna()
    for t, x in grid.iterrows():
        ventana = t + pd.Timedelta(minutes=1)
        for m in MONEDAS:
            otra = [o for o in MONEDAS if o != m][0]
            opin = {"propia": x[f"okx5_{m}"], "otra": x[f"okx5_{otra}"], "p20": x["p20"], "p42": x["p42"],
                    "p51": x["p51"], "p53": x["p53"]}
            p_gran = combinar(coef[m], opin)
            inst = inst_id(m, ventana)
            res, fuente = resultados.get(inst, (None, None))
            out.append({"ventana": ventana.isoformat(), "moneda": m, "instrumento": inst,
                        "opiniones": {k: round(float(v), 5) for k, v in opin.items()},
                        "p_gran": round(p_gran, 5), "p_base": round(float(opin["propia"]), 5),
                        "senal_gran": bool(max(p_gran, 1 - p_gran) - study63.COSTO >= study63.MARGEN),
                        "senal_base": bool(max(opin["propia"], 1 - opin["propia"]) - study63.COSTO >= study63.MARGEN),
                        "horario_usuario": bool(2 <= ventana.hour < 6), "resultado": res, "fuente": fuente})
    return out


# ----------------------------------------------------------------------------------------------- datos del día
_SUB = {"BTCUSDT": None, "ETHUSDT": "eth", "SOLUSDT": "sol"}  # mismas cachés que el registro
_VEN = {"BTCUSDT": "blitz", "ETHUSDT": "blitz_eth", "SOLUSDT": "blitz_sol"}


def _datos_moneda(day: pd.Timestamp, symbol: str, cache: Path):
    from ..research.study3 import spot_bars
    from ..research.study16 import minute_table
    from .anticipada import download_daily

    d1 = day + pd.Timedelta(days=1)
    bin_cache = Path(cache) / _SUB[symbol] if _SUB[symbol] else Path(cache)
    m1 = download_daily("1m", f"{day - pd.Timedelta(days=3):%Y-%m-%d}", f"{d1:%Y-%m-%d}", bin_cache, symbol)
    sec = download_daily("1s", f"{day:%Y-%m-%d}", f"{d1:%Y-%m-%d}", bin_cache, symbol)
    bars = spot_bars(m1[~m1.index.duplicated(keep="last")].sort_index())
    tab = minute_table(sec, pd.date_range(day, d1, freq="min", tz="UTC", inclusive="left")).reindex(bars.index)
    return bars, tab, sec, bin_cache


def _probas(bundle: dict, X: pd.DataFrame, filas: np.ndarray, index: pd.DatetimeIndex) -> pd.Series:
    Xb = X[bundle["features"]]
    ok = filas & Xb.notna().all(axis=1).to_numpy()
    p = bundle["calibrator"].transform(bundle["model"].predict_proba(Xb[ok].to_numpy())[:, 1])
    return pd.Series(p, index=index[ok])


def opiniones_dia(day: str, cache: Path | None = None) -> tuple[pd.DataFrame, dict]:
    """Probabilidad de subir de cada modelo congelado en cada minuto del día (UTC). También devuelve las velas y el
    segundo a segundo de ETH y BTC para reconstruir el resultado cuando no hay oficial."""
    from ..research.features import FEATURES, compute_features
    from ..research.study16 import partial_features
    from ..research.study41 import composite
    from ..research.study42 import comp_features
    from .anticipada import load_bundle
    from .registro import CACHE, _maybe, bybit_closes, okx_closes

    cache = Path(cache or CACHE)
    d0 = pd.Timestamp(day, tz="UTC")
    d1 = d0 + pd.Timedelta(days=1)
    b = {k: load_bundle(*v) for k, v in bases().items()}
    assert all(x["k"] == 50 for x in b.values()), "todas las opiniones deciden en el segundo 50"
    cols, crudos = {}, {}
    for symbol in ("BTCUSDT", "ETHUSDT", "SOLUSDT"):
        bars, tab, sec, bin_cache = _datos_moneda(d0, symbol, cache)
        crudos[symbol] = (bars, sec, bin_cache)
        prev = compute_features(bars).shift(1)
        vol = np.exp(prev["lvol60"])
        ven = cache / _VEN[symbol]
        by = pd.concat([bybit_closes(d0 - pd.Timedelta(days=1), ven, symbol), bybit_closes(d0, ven, symbol),
                        _maybe(bybit_closes, d1, ven, symbol)])
        ok = okx_closes(d0 - pd.Timedelta(hours=2), d1, symbol)
        comp = composite({"binance": bars["c"], "bybit": by[~by.index.duplicated()], "okx": ok[~ok.index.duplicated()]})
        X = pd.concat([prev[FEATURES], partial_features(tab, bars["o"], vol, 50),
                       comp_features(comp, bars["c"], vol, bars.index)], axis=1)
        X = X.loc[:, ~X.columns.duplicated()]
        filas = np.asarray((bars.index >= d0) & (bars.index < d1))
        if symbol == "BTCUSDT":
            cols["okx5_BTCUSDT"] = _probas(b["okx5_BTCUSDT"], X, filas, bars.index)
            cols["p42"] = _probas(b["p42"], X, filas, bars.index)
            cols["p20"] = _probas(b["p20"], X, filas, bars.index)
        elif symbol == "ETHUSDT":
            cols["okx5_ETHUSDT"] = _probas(b["okx5_ETHUSDT"], X, filas, bars.index)
            cols["p51"] = _probas(b["p51"], X, filas, bars.index)
        else:
            cols["p53"] = _probas(b["p53"], X, filas, bars.index)
    return pd.DataFrame(cols), crudos


def oficiales_dentro(d0: pd.Timestamp, d1: pd.Timestamp, carpeta: Path = DENTRO) -> dict[str, tuple[int, str]]:
    """Resultados oficiales que guardó el grabador de dentro de la ventana (todas las ventanas desde el 2026-11-11)."""
    out = {}
    for f in sorted(Path(carpeta).glob("*_resultados.jsonl")):
        for line in f.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                if str(r.get("resultado")) in ("1", "2"):
                    out.setdefault(r["inst"], (1 if str(r["resultado"]) == "1" else -1, "oficial"))
    return out


def resultados_dia(day: str, crudos: dict, filas_t: pd.DatetimeIndex, cache: Path) -> dict[str, tuple[int, str]]:
    """Resultado de cada contrato de 5 min de ETH y BTC del día: oficial (API de OKX o grabador) o reconstruido."""
    from ..research.study54 import SIMBOLOS, settle_labels
    from .anticipada import download_daily
    from .okx_eventos import inst_id
    from .registro import okx_index_closes, okx_resultados

    d0 = pd.Timestamp(day, tz="UTC")
    d1 = d0 + pd.Timedelta(days=1)
    extra = pd.Timedelta(minutes=10)
    out = dict(oficiales_dentro(d0, d1))
    for m in MONEDAS:
        try:
            for inst, r in okx_resultados(m, d0, d1 + extra).items():
                out.setdefault(inst, (1 if r["outcome"] == "1" else -1, "oficial"))
        except Exception:  # noqa: BLE001 - la API de OKX a veces falla; queda el reconstruido
            pass
        faltan = [t for t in filas_t if inst_id(m, t + pd.Timedelta(minutes=1)) not in out]
        if not faltan:
            continue
        bars, sec, bin_cache = crudos[m]
        ix = okx_index_closes(SIMBOLOS[m]["indice"], d0 - pd.Timedelta(minutes=30), d1 + extra)
        try:
            nxt = download_daily("1s", f"{d1:%Y-%m-%d}", f"{d1 + pd.Timedelta(days=1):%Y-%m-%d}", bin_cache, m)
            sec2 = pd.concat([sec, nxt[nxt.index < d1 + extra]])
        except FileNotFoundError:
            sec2 = sec
        sec2 = sec2[~sec2.index.duplicated(keep="last")].sort_index()
        idx = pd.DatetimeIndex(faltan)
        y = settle_labels(idx, 5, ix, bars["c"], sec2.index, sec2["c"].to_numpy(float))
        for t, v in zip(idx, y):
            if not np.isnan(v):
                out[inst_id(m, t + pd.Timedelta(minutes=1))] = (int(v), "reconstruido")
    return out


def gran5_day(day: str, cache: Path | None = None) -> list[dict]:
    from .registro import CACHE

    cache = Path(cache or CACHE)
    coef = json.loads(CONFIG.read_text(encoding="utf-8"))["coeficientes"]
    op, crudos = opiniones_dia(day, cache)
    grid = op[((op.index.minute + 1) % 5) == 0].dropna()
    res = resultados_dia(day, crudos, grid.index, cache)
    return filas_dia(op, coef, res)
