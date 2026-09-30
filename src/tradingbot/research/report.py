"""Agregación de resultados: corrección de Holm, selección MECÁNICA de candidatas e informe.

La selección aplica exactamente los criterios del protocolo (sección 8). No hay intervención manual:
si ninguna configuración los cumple, el veredicto es «SIN SEÑAL».
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from .metrics import holm

KEY = ["symbol", "horizon", "contract", "model", "policy"]


def load_results(results_dir: Path) -> list[dict]:
    files = sorted(Path(results_dir).glob("*.json"))
    return [json.loads(f.read_text()) for f in files if f.name not in ("frozen.json",)]


def evaluations_frame(results: list[dict]) -> pd.DataFrame:
    rows = []
    for r in results:
        for h, hres in r.get("horizons", {}).items():
            for e in hres.get("evaluations", []):
                row = {k: e.get(k) for k in KEY + ["n_trades", "hit", "hit_lo95", "hit_hi95", "breakeven", "ev",
                                                  "ev_lo95", "ev_hi95", "total", "max_drawdown", "pvalue",
                                                  "positive_fold_frac", "max_fold_profit_share", "tie_rate",
                                                  "sensitivity", "is_reference"]}
                row.update({f"n_{k}": v for k, v in e.get("counts", {}).items()})
                rows.append(row)
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    hyp = ~df["sensitivity"].astype(bool)
    df["p_holm"] = np.nan
    df.loc[hyp, "p_holm"] = holm(df.loc[hyp, "pvalue"].fillna(1.0).tolist())
    return df


def select_candidates(df: pd.DataFrame, acc: dict) -> pd.DataFrame:
    """Evalúa los criterios en todas las filas; solo pueden ser candidatas las que no son de
    referencia ni variantes de sensibilidad."""
    if df.empty:
        return df
    d = df.copy()
    ref = d[d["is_reference"].astype(bool) & (d["policy"] == "A") & ~d["sensitivity"].astype(bool)]
    best_ref = ref.groupby(["symbol", "horizon", "contract"])["ev"].max().rename("best_ref_ev")
    d = d.join(best_ref, on=["symbol", "horizon", "contract"])
    is_bin = d["contract"] == "binaria"
    d["c1_min_trades"] = d["n_trades"] >= acc["min_trades"]
    d["c2_above_breakeven"] = np.where(is_bin, d["hit_lo95"] > d["breakeven"], d["ev_lo95"] > 0)
    d["c3_holm"] = d["p_holm"] < acc["alpha"]
    share_ok = d["max_fold_profit_share"].fillna(1.0) <= acc["max_fold_profit_share"]
    d["c4_stable"] = (d["positive_fold_frac"].fillna(0) >= acc["min_positive_fold_frac"]) & share_ok
    d["c5_beats_reference"] = d["ev"] > d["best_ref_ev"]
    crit = ["c1_min_trades", "c2_above_breakeven", "c3_holm", "c4_stable", "c5_beats_reference"]
    d["candidate"] = d[crit].all(axis=1) & ~d["is_reference"].astype(bool) & ~d["sensitivity"].astype(bool)
    return d


def accuracy_target_table(results: list[dict], target: float, min_n: int) -> pd.DataFrame:
    rows = []
    for r in results:
        for h, hres in r.get("horizons", {}).items():
            for m, cov in hres.get("coverage", {}).items():
                ok = [c for c in cov if c["n"] >= min_n and c["hit"] is not None]
                if not ok:
                    continue
                best = max(ok, key=lambda c: c["hit"])
                rows.append({"symbol": r["symbol"], "horizon": int(h), "model": m,
                             "best_hit": best["hit"], "lo95": best["lo95"], "hi95": best["hi95"],
                             "n": best["n"], "coverage": best["realized_coverage"],
                             "reaches_target": bool(best["lo95"] is not None and best["lo95"] >= target)})
    return pd.DataFrame(rows)


def frozen_selection(cands: pd.DataFrame, cfg: dict, stage_meta: dict) -> dict:
    sel = cands[cands["candidate"]] if not cands.empty else cands
    return {
        "generated_by": "selección mecánica (research/report.py)",
        "stage_source": "dev",
        **stage_meta,
        "config": cfg,
        "candidates": [] if sel.empty else sel[KEY].to_dict(orient="records"),
        "verdict": "SIN SEÑAL" if sel.empty else "HAY CANDIDATAS (pendiente periodo bloqueado)",
    }


def _pct(x, digits=1):
    return "—" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{100 * x:.{digits}f} %"


def _num(x, digits=3):
    return "—" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x:.{digits}f}"


def render_markdown(results: list[dict], cands: pd.DataFrame, acc_tab: pd.DataFrame, stage: str,
                    cfg: dict) -> str:
    L: list[str] = []
    meta = results[0] if results else {}
    n_hyp = int((~cands["sensitivity"].astype(bool)).sum()) if not cands.empty else 0
    L.append(f"# Resultados empíricos — etapa `{stage}`\n")
    L.append(f"- Commit del código: `{meta.get('git_sha', '?')}` — hash de configuración: "
             f"`{meta.get('config_hash', '?')}` — versión {meta.get('code_version', '?')}")
    L.append(f"- Hipótesis evaluadas (corrección de Holm sobre todas): **{n_hyp}**")
    L.append("- Contrato binario: pago "
             f"{cfg['contracts']['binary_payout']:.0%}, empate = {cfg['contracts']['binary_tie_rule']}; "
             "contado: spread observado + comisión.\n")

    L.append("## 1. Veredicto mecánico\n")
    sel = cands[cands["candidate"]] if not cands.empty else cands
    if sel.empty:
        L.append("**SIN SEÑAL.** Ninguna combinación de instrumento, horizonte, contrato, modelo y política "
                 "cumple los cinco criterios pre-registrados. El sistema debe operar en modo «sin señal».\n")
    else:
        L.append("Configuraciones candidatas (deben superar además el periodo bloqueado y la observación en vivo):\n")
        L.append("| Instrumento | h | Contrato | Modelo | Política | n | Acierto [IC95] | EV [IC95] | p Holm |")
        L.append("|---|---|---|---|---|---|---|---|---|")
        for _, r in sel.iterrows():
            L.append(f"| {r.symbol} | {r.horizon} | {r.contract} | {r.model} | {r.policy} | {r.n_trades} | "
                     f"{_pct(r.hit)} [{_pct(r.hit_lo95)}, {_pct(r.hit_hi95)}] | {_num(r.ev)} "
                     f"[{_num(r.ev_lo95)}, {_num(r.ev_hi95)}] | {_num(r.p_holm, 4)} |")
        L.append("")
    if not cands.empty:
        crit = ["c1_min_trades", "c2_above_breakeven", "c3_holm", "c4_stable", "c5_beats_reference"]
        nonref = cands[~cands["is_reference"].astype(bool) & ~cands["sensitivity"].astype(bool)]
        L.append("Cuántas configuraciones (no de referencia) cumplen cada criterio por separado:\n")
        L.append("| Criterio | Cumplen | De |")
        L.append("|---|---|---|")
        for c in crit:
            L.append(f"| {c} | {int(nonref[c].sum())} | {len(nonref)} |")
        L.append("")

    L.append("## 2. Calidad de datos\n")
    L.append("| Instrumento | Minutos en sesión | Minutos cerrados | Min. sin ticks aislados | Spread mediano | Desde | Hasta |")
    L.append("|---|---|---|---|---|---|---|")
    for r in results:
        q = r.get("quality", {})
        L.append(f"| {r['symbol']} | {q.get('session_minutes', 0):,} | {q.get('closed_minutes', 0):,} | "
                 f"{q.get('isolated_no_tick_minutes', 0):,} | {_num(q.get('spread_median'), 6)} | "
                 f"{str(q.get('first', ''))[:10]} | {str(q.get('last', ''))[:10]} |")
    L.append("")

    L.append("## 3. Movimiento típico frente a costos (periodo de prueba)\n")
    L.append("Umbral de contado `p* ≈ 0,5 + costo/(2·movimiento)`; si supera 100 % es inalcanzable.\n")
    L.append("| Instrumento | h (min) | Mov. medio abs. (pb) | Costo medio ida y vuelta (pb) | p* contado | Empates |")
    L.append("|---|---|---|---|---|---|")
    for r in results:
        for h, hres in r.get("horizons", {}).items():
            d = hres.get("descriptive")
            if not d:
                continue
            be = d["spot_breakeven"]
            be_txt = _pct(be) + (" (inalcanzable)" if be is not None and be > 1 else "")
            L.append(f"| {r['symbol']} | {h} | {_num(d['mean_abs_move_bps'], 2)} | {_num(d['mean_cost_bps'], 2)} | "
                     f"{be_txt} | {_pct(d['tie_rate'])} |")
    L.append("")

    if not cands.empty:
        L.append("## 4. Acierto fuera de muestra — contrato binario, política A (operar todo)\n")
        L.append(f"Umbral con pago {cfg['contracts']['binary_payout']:.0%}: "
                 f"**{_pct(1 / (1 + cfg['contracts']['binary_payout']), 2)}**. Celdas: acierto (n en miles).\n")
        b = cands[(cands["contract"] == "binaria") & (cands["policy"] == "A") & ~cands["sensitivity"].astype(bool)]
        models = list(dict.fromkeys(b["model"]))
        L.append("| Instrumento | h | " + " | ".join(models) + " |")
        L.append("|---|---|" + "---|" * len(models))
        for (s, h), g in b.groupby(["symbol", "horizon"]):
            cells = []
            for m in models:
                x = g[g["model"] == m]
                cells.append("—" if x.empty else f"{_pct(x.iloc[0].hit)} ({x.iloc[0].n_trades / 1000:.0f}k)")
            L.append(f"| {s} | {h} | " + " | ".join(cells) + " |")
        L.append("")

        L.append("## 5. Políticas selectivas (B = EV estimado ≥ margen; BN = B sin ventanas de noticias)\n")
        L.append("| Instrumento | h | Contrato | Modelo | Política | n | Acierto [IC95] | EV [IC95] | Máx. caída | p Holm |")
        L.append("|---|---|---|---|---|---|---|---|---|---|")
        sb = cands[cands["policy"].isin(["B", "BN"])].sort_values(["symbol", "horizon", "contract", "model", "policy"])
        for _, r in sb.iterrows():
            L.append(f"| {r.symbol} | {r.horizon} | {r.contract} | {r.model} | {r.policy} | {r.n_trades} | "
                     f"{_pct(r.hit)} [{_pct(r.hit_lo95)}, {_pct(r.hit_hi95)}] | {_num(r.ev)} "
                     f"[{_num(r.ev_lo95)}, {_num(r.ev_hi95)}] | {_num(r.max_drawdown, 1)} | {_num(r.p_holm, 3)} |")
        L.append("\nUnidades: binaria en unidades de apuesta; contado en puntos básicos (pb).\n")

    L.append(f"## 6. ¿Se alcanza un acierto ≥ {cfg['acceptance']['target_accuracy']:.0%}?\n")
    L.append(f"Mejor acierto en cualquier nivel de cobertura (umbral fijado con el tramo de calibración, "
             f"n ≥ {cfg['acceptance']['min_n_for_accuracy_claim']}), sin costos.\n")
    if acc_tab.empty:
        L.append("Sin datos.\n")
    else:
        L.append("| Instrumento | h | Modelo | Mejor acierto | IC95 | n | Cobertura | ¿≥ objetivo? |")
        L.append("|---|---|---|---|---|---|---|---|")
        for _, r in acc_tab.sort_values(["symbol", "horizon", "model"]).iterrows():
            L.append(f"| {r.symbol} | {r.horizon} | {r.model} | {_pct(r.best_hit)} | [{_pct(r.lo95)}, {_pct(r.hi95)}] | "
                     f"{r.n} | {_pct(r.coverage, 2)} | {'sí' if r.reaches_target else 'no'} |")
        L.append("")

    L.append("## 7. Calibración fuera de muestra (P(sube))\n")
    L.append("| Instrumento | h | Modelo | ECE | Brier | Brier ref. (0,5) | n |")
    L.append("|---|---|---|---|---|---|---|")
    for r in results:
        for h, hres in r.get("horizons", {}).items():
            for m, c in hres.get("calibration", {}).items():
                L.append(f"| {r['symbol']} | {h} | {m} | {_pct(c['ece'], 2)} | {_num(c['brier'], 5)} | 0,25000 | {c['n']:,} |")
    L.append("")

    if not cands.empty:
        L.append("## 8. Sensibilidad (no son hipótesis nuevas)\n")
        L.append("| Instrumento | h | Contrato | Modelo | Variante | n | Acierto | EV |")
        L.append("|---|---|---|---|---|---|---|---|")
        sens = cands[cands["sensitivity"].astype(bool)] if "sensitivity" in cands else cands.iloc[0:0]
        for _, r in sens.sort_values(["symbol", "horizon", "contract", "model", "policy"]).iterrows():
            L.append(f"| {r.symbol} | {r.horizon} | {r.contract} | {r.model} | {r.policy} | {r.n_trades} | "
                     f"{_pct(r.hit)} | {_num(r.ev)} |")
        L.append("")

    L.append("## 9. Acierto alto ≠ rentabilidad (demostración)\n")
    L.append("Entradas al azar con objetivo de ganancia de 1σ y límite de pérdida de 10σ (σ = volatilidad a 15 min).\n")
    L.append("| Instrumento | n | Objetivo alcanzado («acierto») | Ganadoras netas de costos | EV neto (pb) | "
             "Ganancia media (pb) | Pérdida media (pb) |")
    L.append("|---|---|---|---|---|---|---|")
    for r in results:
        d = r.get("illusion_demo")
        if d and "n" in d:
            L.append(f"| {r['symbol']} | {d['n']:,} | {_pct(d['tp_hit_rate'])} | {_pct(d['win_rate'])} | "
                     f"{_num(d['mean_net_bps'], 2)} | {_num(d.get('avg_win_bps'), 2)} | "
                     f"{_num(d.get('avg_loss_bps'), 2)} |")
    L.append("")
    return "\n".join(L)
