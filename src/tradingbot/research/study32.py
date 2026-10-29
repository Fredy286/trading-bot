"""Estudio 32 (pre-registro en docs/01, commit 5a70ec4): auditoría PROSPECTIVA de canales de señales.

Lee los mensajes capturados cada hora en `results/canales/<canal>/`, extrae las señales con reglas fijas, conserva
solo las publicadas antes de su hora de entrada y las juzga con velas de 1 min de precio medio de Deriv (G0).
Resultados por canal y día en `results/auditoria_canales/<canal>/<día>.jsonl`.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

from ..data.telegram_publico import LISTA, ROOT, channels
from .metrics import binom_pvalue_greater, wilson
from .study22 import holm

OUT = Path("results/auditoria_canales")
DERIV_FX = ("AUDCAD", "AUDCHF", "AUDJPY", "AUDNZD", "AUDUSD", "EURAUD", "EURCAD", "EURCHF", "EURGBP", "EURJPY",
            "EURNZD", "EURUSD", "GBPAUD", "GBPCAD", "GBPCHF", "GBPJPY", "GBPNZD", "GBPUSD", "NZDJPY", "NZDUSD",
            "USDCAD", "USDCHF", "USDJPY", "USDMXN", "USDPLN")
_PAIR = re.compile(r"\b([A-Z]{3})\s*/?\s*([A-Z]{3})\b")
_TIME = re.compile(r"(?<!\d)([01]?\d|2[0-3])[:h]([0-5]\d)(?!\d)")
_TF = re.compile(r"\bM(1|5|15)\b", re.I)
_UP = re.compile(r"\b(CALL|BUY|COMPRA|UP)\b|🟩|⬆|🔼", re.I)
_DOWN = re.compile(r"\b(PUT|SELL|VENDA|VENTA|DOWN)\b|🟥|⬇|🔽", re.I)
START, EVAL_END = "2026-10-29", "2027-01-26"


def parse_signals(text: str, published: pd.Timestamp, tz_h: float | None) -> list[dict]:
    """Señales verificables de un mensaje según las reglas del pre-registro."""
    if tz_h is None or "OTC" in text.upper():  # regla: se excluyen los mensajes que digan «OTC»
        return []
    post_tf = _TF.search(text)
    off = pd.Timedelta(hours=tz_h)
    pub_local = published.tz_convert(None) + off
    out = []
    for ln in text.splitlines():
        pm = [m for m in _PAIR.finditer(ln.upper()) if m.group(1) + m.group(2) in DERIV_FX]
        tm = _TIME.search(ln)
        up, down = bool(_UP.search(ln)), bool(_DOWN.search(ln))
        if not pm or not tm or up == down:
            continue
        tf = _TF.search(ln) or post_tf
        if not tf:
            continue
        local = pub_local.normalize() + pd.Timedelta(hours=int(tm.group(1)), minutes=int(tm.group(2)))
        if local <= pub_local:
            local += pd.Timedelta(days=1)  # primera vez que llega esa hora DESPUÉS de la publicación
        out.append({"par": pm[0].group(1) + pm[0].group(2), "dir": 1 if up else -1, "venc_min": int(tf.group(1)),
                    "entrada_utc": (local - off).tz_localize("UTC").isoformat(), "linea": ln.strip()[:120]})
    return out


def judge(sig: dict, candles: pd.Series, opens: pd.Series) -> str | None:
    t0 = int(pd.Timestamp(sig["entrada_utc"]).timestamp())
    t1 = t0 + 60 * (sig["venc_min"] - 1)
    if t0 not in opens.index or t1 not in candles.index:
        return None
    d = candles[t1] - opens[t0]
    if abs(d) < 1e-9:
        return "empate"
    return "gana" if np.sign(d) == sig["dir"] else "pierde"


def audit_day(day: str, feed=None, root: Path = ROOT, out: Path = OUT, lista: Path = LISTA, log=print) -> dict:
    """Juzga las señales cuya ENTRADA cae en el día `day` (UTC), de mensajes capturados de cualquier día anterior."""
    from ..live.nocturna import DerivFeed

    f = feed or DerivFeed()
    d0 = pd.Timestamp(day, tz="UTC")
    d1 = d0 + pd.Timedelta(days=1)
    cache: dict[str, tuple[pd.Series, pd.Series]] = {}
    summary = {}
    for chan, tz in channels(lista).items():
        rows = []
        for fpath in sorted((Path(root) / chan).glob("20*.jsonl")):
            if fpath.stem < (d0 - pd.Timedelta(days=2)).strftime("%Y-%m-%d") or fpath.stem > day:
                continue
            for line in fpath.read_text(encoding="utf-8").splitlines():
                m = json.loads(line)
                if not m.get("publicado_utc") or m["publicado_utc"] < START:
                    continue
                pub = pd.Timestamp(m["publicado_utc"])
                for s in parse_signals(m.get("texto", ""), pub, tz):
                    if not (d0 <= pd.Timestamp(s["entrada_utc"]) < d1):
                        continue
                    if s["par"] not in cache:
                        r = f._call({"ticks_history": f"frx{s['par']}", "style": "candles", "granularity": 60,
                                     "count": 5000, "start": int(d0.timestamp()), "end": int(d1.timestamp()) + 1800})
                        c = pd.DataFrame(r.get("candles", []))
                        cache[s["par"]] = ((c.set_index("epoch")["close"].astype(float), c.set_index("epoch")["open"].astype(float))
                                           if len(c) else (pd.Series(dtype=float), pd.Series(dtype=float)))
                    closes, opens = cache[s["par"]]
                    rows.append({**s, "canal": chan, "mensaje": m["id"], "publicado_utc": m["publicado_utc"],
                                 "editado_al_capturar": m.get("editado"), "capturado_utc": m.get("capturado_utc"),
                                 "resultado": judge(s, closes, opens)})
        if rows:
            p = Path(out) / chan / f"{day}.jsonl"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
        summary[chan] = len(rows)
    log(f"auditoría {day}: {summary}")
    return summary


def audit_pending(out: Path = OUT, log=print) -> None:
    """Audita los días completos (desde el inicio) que aún no tengan marca de hecho."""
    done_f = Path(out) / "dias_auditados.txt"
    done = set(done_f.read_text(encoding="utf-8").split()) if done_f.exists() else set()
    last = (pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    for d in pd.date_range(START, last, freq="D"):
        day = d.strftime("%Y-%m-%d")
        if day in done:
            continue
        audit_day(day, log=log)
        done.add(day)
    Path(out).mkdir(parents=True, exist_ok=True)
    done_f.write_text("\n".join(sorted(done)) + "\n", encoding="utf-8")


def table(out: Path = OUT, until: str | None = None) -> dict:
    """Tabla descriptiva por canal (sin veredicto antes del 2027-01-31; después, con H32)."""
    res = {}
    for folder in sorted(p for p in Path(out).iterdir() if p.is_dir()) if Path(out).exists() else []:
        rows = [json.loads(ln) for f in sorted(folder.glob("*.jsonl")) for ln in f.read_text(encoding="utf-8").splitlines()]
        rows = [r for r in rows if until is None or r["publicado_utc"] < until]
        n = sum(r["resultado"] in ("gana", "pierde") for r in rows)
        w = sum(r["resultado"] == "gana" for r in rows)
        lo, _ = wilson(w, n) if n else (float("nan"), 0)
        res[folder.name] = {"senales": len(rows), "verificadas": n, "acierto_g0": w / n if n else None,
                            "lo95": float(lo), "p_azar": binom_pvalue_greater(w, n, 0.5) if n else 1.0}
    big = [k for k, v in res.items() if v["verificadas"] >= 100]
    for k, pa in zip(big, holm([res[k]["p_azar"] for k in big])):
        res[k]["p_holm"] = pa
    return res
