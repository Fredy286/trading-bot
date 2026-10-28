"""Estudio 23 (pre-registro en docs/01, commit 11054d0): auditoría de señales de canales de Telegram con precios reales.

Cada señal no OTC se lee con reglas fijas (zona horaria, fecha, vencimiento), se conserva solo si se publicó ANTES
de la hora de entrada y se juzga con velas de 1 min de HistData (bid): apertura de la vela de entrada contra cierre de
la última vela del vencimiento. Se mide la primera entrada (G0).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

from .experiment import git_sha, jsonable
from .metrics import binom_pvalue_greater, wilson
from .study22 import holm

BE = 1 / 1.85
MIN_N = 300
TZ_RE = re.compile(r"UTC\s*([+\-−])\s*(\d{1,2})(?::?(\d{2}))?")
SIGNALS = Path("data/raw/senales_terceros")
PRICES = Path("data/raw/histdata_pares")


def tz_offset(text: str) -> float | None:
    """Horas respecto de UTC; los canales brasileños sin zona declarada usan Brasília (UTC−3)."""
    m = TZ_RE.search(str(text))
    if m:
        sign = -1 if m.group(1) in "-−" else 1
        return sign * (int(m.group(2)) + int(m.group(3) or 0) / 60)
    if "brasileñ" in str(text).lower():
        return -3.0
    return None


def entry_utc(text: str, published: pd.Timestamp, offset_h: float) -> pd.Timestamp | None:
    """Hora de entrada en UTC según el pre-registro (fecha completa, día/mes sin año, o solo la hora)."""
    t = str(text).strip()
    off = pd.Timedelta(hours=offset_h)
    pub_local = published.tz_convert(None) + off
    m = re.match(r"^(\d{1,2})[/-](\d{1,2})[/-](\d{4})\s+(\d{1,2}):(\d{2})", t)
    if m:
        d, mo, y, hh, mm = map(int, m.groups())
        local = pd.Timestamp(year=y, month=mo, day=d, hour=hh, minute=mm)
        return (local - off).tz_localize("UTC")
    m = re.match(r"^(\d{1,2})[/-](\d{1,2})\s+(\d{1,2}):(\d{2})", t)
    if m:
        d, mo, hh, mm = map(int, m.groups())
        cands = []
        for y in (pub_local.year - 1, pub_local.year, pub_local.year + 1):
            try:
                cands.append(pd.Timestamp(year=y, month=mo, day=d, hour=hh, minute=mm))
            except ValueError:
                pass
        if not cands:
            return None
        local = min(cands, key=lambda c: abs(c - pub_local))
        return (local - off).tz_localize("UTC")
    m = re.match(r"^(\d{1,2}):(\d{2})(?::\d{2})?$", t)
    if m:
        hh, mm = map(int, m.groups())
        local = pub_local.normalize() + pd.Timedelta(hours=hh, minutes=mm)
        if local <= pub_local:
            local += pd.Timedelta(days=1)  # primera vez que llega esa hora DESPUÉS de la publicación
        return (local - off).tz_localize("UTC")
    return None


def read_channel(f: Path) -> pd.DataFrame:
    d = pd.read_csv(f)
    d = d[d["es_otc"].astype(str).str.lower().isin(["no", "false"])].copy()
    d["canal"] = f.stem
    d["par"] = d["activo"].astype(str).str.replace("/", "").str.upper()
    d["pub"] = pd.to_datetime(d["publicado_utc"], utc=True, errors="coerce")
    d["dir"] = d["direccion"].astype(str).str.upper().map({"CALL": 1, "PUT": -1, "COMPRA": 1, "VENTA": -1})
    venc = pd.to_numeric(d["vencimiento_min"], errors="coerce")
    modal = venc.mode()
    d["venc"] = venc.fillna(modal.iloc[0] if len(modal) else np.nan)  # nota de implementación del pre-registro
    if f.stem == "binomo_vip_ind":
        d["entrada"] = d["pub"].dt.floor("min") + pd.Timedelta(minutes=1)
        d["venc"] = 5.0
    else:
        offs = d["zona_horaria_declarada"].map(tz_offset)
        d["entrada"] = [entry_utc(t, p, o) if pd.notna(p) and o is not None else None
                        for t, p, o in zip(d["hora_entrada_texto"], d["pub"], offs)]
        d["offset_h"] = offs
    d["entrada"] = pd.to_datetime(d["entrada"], utc=True)
    return d


class Prices:
    def __init__(self, root: Path = PRICES):
        self.root, self.cache = Path(root), {}

    def get(self, pair: str) -> pd.DataFrame | None:
        if pair not in self.cache:
            files = sorted((self.root / pair).glob("*.parquet"))
            if not files:
                self.cache[pair] = None
            else:
                df = pd.concat([pd.read_parquet(f) for f in files]).sort_index()
                df = df[~df.index.duplicated(keep="last")]
                self.cache[pair] = df[["bid_o", "bid_c"]]
        return self.cache[pair]


def outcome(px: pd.DataFrame | None, entry: pd.Series, venc: pd.Series) -> np.ndarray:
    """Signo de (cierre de la última vela del vencimiento − apertura de la vela de entrada); NaN si falta alguna."""
    if px is None or len(entry) == 0:
        return np.full(len(entry), np.nan)
    o = px["bid_o"].reindex(pd.DatetimeIndex(entry)).to_numpy()
    last = pd.DatetimeIndex(entry) + pd.to_timedelta(venc.to_numpy() - 1, unit="min")
    c = px["bid_c"].reindex(last).to_numpy()
    d = c - o
    return np.where(np.isnan(d), np.nan, np.sign(np.where(np.abs(d) < 1e-9, 0.0, d)))


def summarize(g: pd.DataFrame) -> dict:
    r = (g["dir"] * g["res"]).to_numpy()
    n, w, ties = int((r != 0).sum()), int((r > 0).sum()), int((r == 0).sum())
    lo, _ = wilson(w, n) if n else (float("nan"), 0)
    pnl = np.where(r == 0, 0.0, np.where(r > 0, 0.85, -1.0))
    return {"verificables": int(len(g)), "sin_empate": n, "aciertos": w, "empates": ties,
            "acierto": w / n if n else None, "lo95": float(lo), "ev": float(pnl.mean()) if len(pnl) else None,
            "p_azar": binom_pvalue_greater(w, n, 0.5) if n else 1.0}


def run(out_dir: Path = Path("results/estudio23"), log=print) -> dict:
    prices = Prices()
    chans = [read_channel(f) for f in sorted(SIGNALS.glob("*.csv"))]
    rep = {"estudio": "Estudio 23 — auditoría de canales (pre-registro 11054d0)", "git_sha": git_sha(), "canales": {}}
    for d in chans:
        if not len(d):
            continue
        name = d["canal"].iloc[0]
        ok = d["dir"].notna() & d["entrada"].notna() & d["venc"].notna()
        before = ok & (d["pub"] < d["entrada"])
        d = d.assign(res=np.nan)
        for pair, idx in d[before].groupby("par").groups.items():
            sub = d.loc[idx]
            d.loc[idx, "res"] = outcome(prices.get(pair), sub["entrada"], sub["venc"])
        v = d[before & d["res"].notna()]
        info = {"no_otc": int(len(d)), "legibles": int(ok.sum()), "publicadas_antes": int(before.sum()),
                "publicadas_despues": int((ok & ~before).sum()), **summarize(v)}
        # Declarado frente a medido (solo G0: «WIN» del canal)
        dec = v["resultado_declarado"].astype(str).str.upper()
        win_decl = dec == "WIN"
        if win_decl.any():
            rr = (v["dir"] * v["res"])[win_decl]
            info["declara_win_y_el_precio_dice_perdida"] = float((rr < 0).mean())
            info["declara_win_n"] = int(win_decl.sum())
        known = dec.isin(["WIN", "G1", "G2", "LOSS", "DOJI"])
        if known.any():
            info["acierto_declarado_g0"] = float((dec[known] == "WIN").mean())
            info["acierto_declarado_con_gale"] = float(dec[known].isin(["WIN", "G1", "G2"]).mean())
        # Control de zona horaria: desplazar la entrada de −5 a +1 h
        if name != "binomo_vip_ind" and len(v):
            shift = {}
            for h in range(-5, 2):
                e2 = v["entrada"] + pd.Timedelta(hours=h)
                res2 = np.full(len(v), np.nan)
                for pair, idx in v.groupby("par").groups.items():
                    pos = v.index.get_indexer(idx)
                    res2[pos] = outcome(prices.get(pair), e2.loc[idx], v.loc[idx, "venc"])
                rr = v["dir"].to_numpy() * res2
                m = ~np.isnan(rr) & (rr != 0)
                shift[f"{h:+d}h"] = float((rr[m] > 0).mean()) if m.any() else None
            info["control_zona_horaria"] = shift
        info["por_par"] = {p: summarize(g)["acierto"] for p, g in v.groupby("par") if len(g) >= 50}
        rep["canales"][name] = info
        log(f"{name}: {info['sin_empate']} verificables, acierto {info['acierto']}")
    big = [k for k, x in rep["canales"].items() if x["sin_empate"] >= MIN_N]
    adj = holm([rep["canales"][k]["p_azar"] for k in big])
    for k, pa in zip(big, adj):
        x = rep["canales"][k]
        x.update({"p_holm_azar": pa, "H23_azar": pa < 0.05, "H23_rentable": x["lo95"] > BE})
    rep["canales_evaluados"] = big
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "resultado.json").write_text(json.dumps(jsonable(rep), indent=2, ensure_ascii=False), encoding="utf-8")
    return rep
