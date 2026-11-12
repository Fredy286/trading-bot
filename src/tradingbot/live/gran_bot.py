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
    usadas = ["okx5_ETHUSDT", "okx5_BTCUSDT", "p20", "p42", "p51", "p53"]
    grid = op.loc[((op.index.minute + 1) % 5) == 0, usadas].dropna()
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
_SUB = {"BTCUSDT": None, "ETHUSDT": "eth", "SOLUSDT": "sol", "XRPUSDT": "xrp", "DOGEUSDT": "doge"}  # cachés del registro
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


def opiniones_dia(day: str, cache: Path | None = None, extra: bool = False) -> tuple[pd.DataFrame, dict]:
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
    b = {k: load_bundle(*v) for k, v in {**bases(), **(bases_extra() if extra else {})}.items()}
    assert all(x["k"] == 50 for x in b.values()), "todas las opiniones deciden en el segundo 50"
    cols, crudos = {}, {}
    for symbol in ("BTCUSDT", "ETHUSDT", "SOLUSDT"):
        bars, tab, sec, bin_cache = _datos_moneda(d0, symbol, cache)
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
        crudos[symbol] = (bars, sec, bin_cache, by, ok)
        if symbol == "BTCUSDT":
            cols["okx5_BTCUSDT"] = _probas(b["okx5_BTCUSDT"], X, filas, bars.index)
            cols["p42"] = _probas(b["p42"], X, filas, bars.index)
            cols["p20"] = _probas(b["p20"], X, filas, bars.index)
            if extra:
                cols["okx15_BTCUSDT"] = _probas(b["okx15_BTCUSDT"], X, filas, bars.index)
        elif symbol == "ETHUSDT":
            cols["okx5_ETHUSDT"] = _probas(b["okx5_ETHUSDT"], X, filas, bars.index)
            cols["p51"] = _probas(b["p51"], X, filas, bars.index)
            if extra:
                cols["okx15_ETHUSDT"] = _probas(b["okx15_ETHUSDT"], X, filas, bars.index)
                cols["e26_eth"] = _probas(b["e26_eth"], X, filas, bars.index)
        else:
            cols["p53"] = _probas(b["p53"], X, filas, bars.index)
            if extra:
                cols["e26_sol"] = _probas(b["e26_sol"], X, filas, bars.index)
    if extra:  # XRP y DOGE: solo sus velas de Binance (receta H16b)
        for symbol in ("XRPUSDT", "DOGEUSDT"):
            bars, tab, sec, _ = _datos_moneda(d0, symbol, cache)
            prev = compute_features(bars).shift(1)
            X = pd.concat([prev[FEATURES], partial_features(tab, bars["o"], np.exp(prev["lvol60"]), 50)], axis=1)
            filas = np.asarray((bars.index >= d0) & (bars.index < d1))
            cols[f"e26_{symbol[:-4].lower()}"] = _probas(b[f"e26_{symbol[:-4].lower()}"], X, filas, bars.index)
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


def resultados_dia(day: str, crudos: dict, filas_t: pd.DatetimeIndex, cache: Path,
                   dur: int = 5) -> dict[str, tuple[int, str]]:
    """Resultado de cada contrato de 5 o 15 min de ETH y BTC del día: oficial (API de OKX o grabador) o reconstruido."""
    from ..research.study54 import SIMBOLOS, settle_labels
    from .anticipada import download_daily
    from .okx_eventos import inst_id
    from .registro import okx_index_closes, okx_resultados

    d0 = pd.Timestamp(day, tz="UTC")
    d1 = d0 + pd.Timedelta(days=1)
    extra = pd.Timedelta(minutes=dur + 5)
    out = dict(oficiales_dentro(d0, d1))
    for m in MONEDAS:
        try:
            for inst, r in okx_resultados(m, d0, d1 + extra, dur=dur).items():
                out.setdefault(inst, (1 if r["outcome"] == "1" else -1, "oficial"))
        except Exception:  # noqa: BLE001 - la API de OKX a veces falla; queda el reconstruido
            pass
        faltan = [t for t in filas_t if inst_id(m, t + pd.Timedelta(minutes=1), dur) not in out]
        if not faltan:
            continue
        bars, sec, bin_cache = crudos[m][:3]
        ix = okx_index_closes(SIMBOLOS[m]["indice"], d0 - pd.Timedelta(minutes=30), d1 + extra)
        try:
            nxt = download_daily("1s", f"{d1:%Y-%m-%d}", f"{d1 + pd.Timedelta(days=1):%Y-%m-%d}", bin_cache, m)
            sec2 = pd.concat([sec, nxt[nxt.index < d1 + extra]])
        except FileNotFoundError:
            sec2 = sec
        sec2 = sec2[~sec2.index.duplicated(keep="last")].sort_index()
        idx = pd.DatetimeIndex(faltan)
        y = settle_labels(idx, dur, ix, bars["c"], sec2.index, sec2["c"].to_numpy(float))
        for t, v in zip(idx, y):
            if not np.isnan(v):
                out[inst_id(m, t + pd.Timedelta(minutes=1), dur)] = (int(v), "reconstruido")
    return out


def gran5_day(day: str, cache: Path | None = None) -> list[dict]:
    from .registro import CACHE

    cache = Path(cache or CACHE)
    coef = json.loads(CONFIG.read_text(encoding="utf-8"))["coeficientes"]
    op, crudos = opiniones_dia(day, cache)
    usadas = ["okx5_ETHUSDT", "okx5_BTCUSDT", "p20", "p42", "p51", "p53"]
    grid = op.loc[((op.index.minute + 1) % 5) == 0, usadas].dropna()
    res = resultados_dia(day, crudos, grid.index, cache)
    return filas_dia(op, coef, res)


# ----------------------------------------------------------------------------------------------- Estudios 68 y 69
OPINIONES_BLITZ = ("propia", "p51", "p53", "p20", "e26_eth", "e26_sol", "e26_xrp", "e26_doge")  # Estudio 66
OPINIONES_15 = ("propia15", "otra15", "propia5", "otra5", "p20", "p42", "p51", "p53")  # Estudio 67
CONFIG_BLITZ = Path("config/gran_bot_blitz.json")
CONFIG_15 = Path("config/gran_bot_okx15.json")
REGISTRO_68_69 = "Estudios 68 y 69 (pre-registro 238985c): metamodelo congelado, ajustado una vez con todo su desarrollo"


def bases_extra() -> dict[str, tuple[Path, Path]]:
    from ..research import study35
    from .okx_eventos import MODELOS15

    uno = {f"e26_{c[:-4].lower()}": (Path(f"config/modelos/{c}_senal_anticipada_k50.pkl"),
                                     Path(f"config/senal_anticipada_{c[:-4].lower()}.json"))
           for c in ("SOLUSDT", "XRPUSDT", "DOGEUSDT")}
    return {"okx15_ETHUSDT": MODELOS15["ETHUSDT"], "okx15_BTCUSDT": MODELOS15["BTCUSDT"],
            "e26_eth": (study35.MODEL_PATH, study35.REG_PATH), **uno}


def _info_bases(claves) -> dict:
    todo = {**bases(), **bases_extra()}
    out = {}
    for k in claves:
        r = json.loads(Path(todo[k][1]).read_text(encoding="utf-8"))
        out[k] = {"model_id": r["model_id"], "model_sha256": r["model_sha256"], "archivo": str(todo[k][0])}
    return out


def _guardar(destino: Path, meta: dict, log) -> dict:
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    log(f"Metamodelo congelado en {destino}")
    return meta


def congelar_blitz(log=print, destino: Path | None = None) -> dict:
    """Metamodelo del gran bot del blitz (Estudio 66), ajustado UNA vez con todo el desarrollo, sin los empates."""
    from ..research import study66

    destino = Path(destino or CONFIG_BLITZ)
    if destino.exists():
        raise FileExistsError(f"{destino} ya existe: el metamodelo se ajusta una sola vez (pre-registro).")
    df = study66.tabla()
    ok = df["y"].to_numpy() != 0
    b = study63.logistica(study63.logit(df[list(OPINIONES_BLITZ)].to_numpy())[ok], (df["y"].to_numpy()[ok] > 0).astype(float))
    meta = {"coeficientes": dict(zip(("constante", *OPINIONES_BLITZ), (float(x) for x in b))),
            "opiniones": list(OPINIONES_BLITZ), "filas_ajuste": int(ok.sum()), "periodo_ajuste": ["2025-09-01", "2026-10-25"],
            "bases": _info_bases(("p42", "p51", "p53", "p20", "e26_eth", "e26_sol", "e26_xrp", "e26_doge")),
            "pago": study66.PAGO, "margen": study66.MARGEN, "git_sha": git_sha(), "creado": utcnow().isoformat(),
            "registro": REGISTRO_68_69}
    return _guardar(destino, meta, log)


def congelar_okx15(log=print, destino: Path | None = None) -> dict:
    """Metamodelo del gran bot de OKX 15 min (Estudio 67), uno por moneda, ajustado UNA vez con todo el desarrollo."""
    from ..research import study67

    destino = Path(destino or CONFIG_15)
    if destino.exists():
        raise FileExistsError(f"{destino} ya existe: el metamodelo se ajusta una sola vez (pre-registro).")
    p54 = pd.read_parquet(study63.P54)
    otras = {k: pd.read_parquet(f)["p"] for k, f in study63.FUENTES.items()}
    coef, filas = {}, {}
    for m in MONEDAS:
        df = study67.tabla(m, p54, otras)
        b = study63.logistica(study63.logit(df[list(OPINIONES_15)].to_numpy()), (df["y"].to_numpy() > 0).astype(float))
        coef[m] = dict(zip(("constante", *OPINIONES_15), (float(x) for x in b)))
        filas[m] = int(len(df))
    meta = {"coeficientes": coef, "opiniones": list(OPINIONES_15), "filas_ajuste": filas,
            "periodo_ajuste": ["2025-09-01", "2026-10-25"],
            "bases": _info_bases(("okx15_ETHUSDT", "okx15_BTCUSDT", "okx5_ETHUSDT", "okx5_BTCUSDT", "p20", "p42", "p51",
                                  "p53")),
            "costo": study63.COSTO, "margen": study63.MARGEN, "git_sha": git_sha(), "creado": utcnow().isoformat(),
            "registro": REGISTRO_68_69}
    return _guardar(destino, meta, log)


def _combinar_con(coef: dict, opiniones: dict[str, float], claves) -> float:
    z = coef["constante"] + sum(coef[k] * float(study63.logit(opiniones[k])) for k in claves)
    return 1 / (1 + math.exp(-max(min(z, 30.0), -30.0)))


_MEMO: dict = {}


def _opiniones_extra(day: str, cache: Path):
    """Las opiniones del día con las extra, calculadas una sola vez por proceso (gran15 y granblitz las comparten)."""
    clave = (day, str(cache))
    if clave not in _MEMO:
        _MEMO.clear()
        _MEMO[clave] = opiniones_dia(day, cache, extra=True)
    return _MEMO[clave]


def filas_15(op: pd.DataFrame, coef: dict, resultados: dict[str, tuple[int, str]]) -> list[dict]:
    from .okx_eventos import inst_id

    out = []
    usadas = ["okx15_ETHUSDT", "okx15_BTCUSDT", "okx5_ETHUSDT", "okx5_BTCUSDT", "p20", "p42", "p51", "p53"]
    grid = op.loc[((op.index.minute + 1) % 15) == 0, usadas].dropna()
    for t, x in grid.iterrows():
        ventana = t + pd.Timedelta(minutes=1)
        for m in MONEDAS:
            otra = [o for o in MONEDAS if o != m][0]
            opin = {"propia15": x[f"okx15_{m}"], "otra15": x[f"okx15_{otra}"], "propia5": x[f"okx5_{m}"],
                    "otra5": x[f"okx5_{otra}"], "p20": x["p20"], "p42": x["p42"], "p51": x["p51"], "p53": x["p53"]}
            p_gran = _combinar_con(coef[m], opin, OPINIONES_15)
            inst = inst_id(m, ventana, 15)
            res, fuente = resultados.get(inst, (None, None))
            out.append({"ventana": ventana.isoformat(), "moneda": m, "instrumento": inst,
                        "opiniones": {k: round(float(v), 5) for k, v in opin.items()},
                        "p_gran": round(p_gran, 5), "p_base": round(float(opin["propia15"]), 5),
                        "senal_gran": bool(max(p_gran, 1 - p_gran) - study63.COSTO >= study63.MARGEN),
                        "senal_base": bool(max(opin["propia15"], 1 - opin["propia15"]) - study63.COSTO >= study63.MARGEN),
                        "horario_usuario": bool(2 <= ventana.hour < 6), "resultado": res, "fuente": fuente})
    return out


def gran15_day(day: str, cache: Path | None = None) -> list[dict]:
    from .registro import CACHE

    cache = Path(cache or CACHE)
    coef = json.loads(CONFIG_15.read_text(encoding="utf-8"))["coeficientes"]
    op, crudos = _opiniones_extra(day, cache)
    usadas = ["okx15_ETHUSDT", "okx15_BTCUSDT", "okx5_ETHUSDT", "okx5_BTCUSDT", "p20", "p42", "p51", "p53"]
    grid = op.loc[((op.index.minute + 1) % 15) == 0, usadas].dropna()
    res = resultados_dia(day, crudos, grid.index, cache, dur=15)
    return filas_15(op, coef, res)


def filas_blitz(op: pd.DataFrame, coef: dict, q: float, y3: pd.Series) -> list[dict]:
    """Velas donde opera el gran bot del blitz o la base (p42), con su resultado del compuesto a 3 min (±1, 0 empate)."""
    from ..research.contracts import BinaryContract

    usadas = ["p42", "p51", "p53", "p20", "e26_eth", "e26_sol", "e26_xrp", "e26_doge"]
    d = op[usadas].dropna()
    contrato = BinaryContract(0.86, "refund")
    out = []
    for t, x in d.iterrows():
        opin = {"propia": x["p42"], **{k: x[k] for k in usadas[1:]}}
        p_gran = _combinar_con(coef, opin, OPINIONES_BLITZ)
        ev = {k: float(contrato.ev(np.array([max(p, 1 - p)]), np.array([q]))[0]) for k, p in
              (("gran", p_gran), ("base", float(x["p42"])))}
        sg, sb = ev["gran"] >= 0.02, ev["base"] >= 0.02
        if not (sg or sb):
            continue
        r = y3.get(t, np.nan)
        out.append({"vela": t.isoformat(), "opiniones": {k: round(float(v), 5) for k, v in opin.items()},
                    "p_gran": round(p_gran, 5), "p_base": round(float(x["p42"]), 5), "q": round(q, 5),
                    "senal_gran": bool(sg), "senal_base": bool(sb), "horario_usuario": bool(2 <= t.hour < 6),
                    "resultado": None if np.isnan(r) else int(r)})
    return out


def granblitz_day(day: str, cache: Path | None = None) -> list[dict]:
    from ..research.study41 import composite
    from ..research.study42 import label3
    from .anticipada import download_daily, load_bundle
    from .blitz import MODELOS as BLITZ
    from .registro import CACHE, _maybe, bybit_closes, okx_closes

    cache = Path(cache or CACHE)
    cfg = json.loads(CONFIG_BLITZ.read_text(encoding="utf-8"))
    op, crudos = _opiniones_extra(day, cache)
    d0 = pd.Timestamp(day, tz="UTC")
    d1 = d0 + pd.Timedelta(days=1)
    bars, sec, bin_cache, by, _ = crudos["BTCUSDT"]
    bn = bars["c"]
    try:  # el resultado de las últimas velas cierra en el día siguiente
        m_next = download_daily("1m", f"{d1:%Y-%m-%d}", f"{d1 + pd.Timedelta(days=1):%Y-%m-%d}", bin_cache, "BTCUSDT")
        bn = pd.concat([bn, m_next.loc[m_next.index < d1 + pd.Timedelta(minutes=6), "c"]])
    except FileNotFoundError:
        pass
    bn = bn[~bn.index.duplicated(keep="last")].sort_index()
    ven = cache / _VEN["BTCUSDT"]
    by2 = pd.concat([by, _maybe(bybit_closes, d1, ven, "BTCUSDT")])
    ok2 = okx_closes(d0 - pd.Timedelta(hours=2), d1 + pd.Timedelta(minutes=5), "BTCUSDT")
    comp = composite({"binance": bn, "bybit": by2[~by2.index.duplicated()], "okx": ok2[~ok2.index.duplicated()]})
    idx = op.index
    y3 = pd.Series(label3(comp, idx), index=idx)
    q = float(load_bundle(*BLITZ["BTCUSDT"])["q"])
    return filas_blitz(op, cfg["coeficientes"], q, y3)
