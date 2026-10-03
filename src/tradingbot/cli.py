"""Interfaz de línea de comandos: `tbot <comando>`.

Ejemplos:
  tbot data download --symbols EURUSD,BTCUSDT --start 2021-01-01 --end 2026-09-01
  tbot research run --symbol EURUSD --stage dev
  tbot research report --stage dev
  tbot alerts example
  tbot alerts demo
  tbot serve
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from . import __version__


def _d(s: str) -> date:
    return date.fromisoformat(s)


# ---------------------------------------------------------------- datos
def cmd_data_download(a) -> int:
    from .data import store
    from .instruments import get_instrument

    for sym in a.symbols.split(","):
        inst = get_instrument(sym.strip())
        store.ensure_downloaded(inst, _d(a.start), _d(a.end), Path(a.root), workers=a.workers, source=a.source)
    return 0


def cmd_data_synth(a) -> int:
    from .data import store, synthetic
    from .instruments import get_instrument

    inst = get_instrument("SYNTH")
    df = synthetic.generate(start=a.start, days=a.days, phi=a.phi, seed=a.seed)
    for year, g in df.groupby(df.index.year):
        p = store.write_year(g, Path(a.root), inst, int(year), g.index.min().date(), g.index.max().date())
        print(f"SINTÉTICO {year}: {len(g):,} velas → {p}")
    return 0


def cmd_data_import_histdata(a) -> int:
    from .data import histdata, store
    from .instruments import get_instrument

    inst = get_instrument(a.symbol)
    df = histdata.load_path(a.path, inst, assumed_spread=a.spread_pips * inst.pip)
    for year, g in df.groupby(df.index.year):
        p = store.write_year(g, Path(a.root), inst, int(year), g.index.min().date(), g.index.max().date())
        print(f"{inst.symbol} {year}: {len(g):,} velas (HistData, spread supuesto {a.spread_pips} pips) → {p}")
    return 0


def cmd_data_probe(a) -> int:
    from .data import probe

    probe.run(pause_s=a.pause)
    return 0


def cmd_data_quality(a) -> int:
    from .data import store
    from .data.clean import to_canonical
    from .instruments import get_instrument

    inst = get_instrument(a.symbol)
    _, rep = to_canonical(store.load(Path(a.root), inst, source=a.source), fill_gaps=(a.source == "histdata"))
    print(json.dumps(rep, indent=2, ensure_ascii=False))
    return 0


# ---------------------------------------------------------------- investigación
def cmd_research_run(a) -> int:
    from .data import store
    from .instruments import get_instrument
    from .research.experiment import config_hash, git_sha, load_config, run_symbol
    from .timeutil import utcnow

    cfg = load_config(a.config)
    if a.stage == "holdout":
        frozen = Path(a.frozen)
        if not frozen.exists():
            print("ERROR: el periodo bloqueado exige config/frozen.json generado por la etapa dev.", file=sys.stderr)
            return 2
        fz = json.loads(frozen.read_text())
        if fz.get("config_hash") != config_hash(cfg):
            print("ERROR: la configuración cambió respecto a la congelada; no se evalúa el periodo bloqueado.",
                  file=sys.stderr)
            return 2
    inst = get_instrument(a.symbol)
    raw = store.load(Path(a.root), inst, source=a.source)
    res = run_symbol(inst.symbol, raw, a.stage, cfg, n_boot=a.n_boot, source=a.source)
    out_dir = Path(a.out) / a.stage
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{inst.symbol}.json").write_text(json.dumps(res, ensure_ascii=False))
    reg = Path(a.out) / "registry.jsonl"
    n_eval = sum(len(h.get("evaluations", [])) for h in res["horizons"].values())
    with open(reg, "a") as fh:
        fh.write(json.dumps({"time_utc": utcnow().isoformat(), "stage": a.stage, "symbol": inst.symbol,
                             "config_hash": config_hash(cfg), "git_sha": git_sha(), "n_evaluations": n_eval,
                             "runtime_s": res.get("runtime_s")}) + "\n")
    print(f"Resultados: {out_dir / (inst.symbol + '.json')} ({n_eval} evaluaciones)")
    return 0


def cmd_research_report(a) -> int:
    from .research import report
    from .research.experiment import config_hash, git_sha, load_config

    cfg = load_config(a.config)
    rdir = Path(a.out) / a.stage
    results = report.load_results(rdir)
    if not results:
        print(f"No hay resultados en {rdir}", file=sys.stderr)
        return 2
    df = report.evaluations_frame(results)
    cands = report.select_candidates(df, cfg["acceptance"])
    acc = report.accuracy_target_table(results, cfg["acceptance"]["target_accuracy"],
                                       cfg["acceptance"]["min_n_for_accuracy_claim"])
    md = report.render_markdown(results, cands, acc, a.stage, cfg)
    if a.stage == "holdout" and Path(a.frozen).exists():
        frozen = json.loads(Path(a.frozen).read_text())
        dev_csv = Path(a.out) / "dev" / "all_evaluations.csv"
        import pandas as pd
        dev_df = pd.read_csv(dev_csv) if dev_csv.exists() else None
        v = report.holdout_verdict(frozen, df, dev_df, cfg["acceptance"]["alpha"])
        (rdir / "verdict.json").write_text(json.dumps(v, indent=2, ensure_ascii=False, default=str))
        md = report.render_holdout_verdict(v) + "\n" + md
        print(f"Veredicto del periodo bloqueado: {v['verdict']}")
    (rdir / "summary.md").write_text(md)
    cands.to_csv(rdir / "all_evaluations.csv", index=False)
    if a.stage == "dev":
        fz = report.frozen_selection(cands, cfg, {"config_hash": config_hash(cfg), "git_sha": git_sha()})
        Path(a.frozen).parent.mkdir(parents=True, exist_ok=True)
        Path(a.frozen).write_text(json.dumps(fz, indent=2, ensure_ascii=False, default=str))
        print(f"Selección congelada: {a.frozen} — veredicto: {fz['verdict']}")
    print(md if a.print else f"Informe: {rdir / 'summary.md'}")
    return 0


# ---------------------------------------------------------------- alertas / app
def cmd_alerts_example(a) -> int:
    from .signals.alert import fictitious_example

    print(fictitious_example())
    return 0


def cmd_alerts_demo(a) -> int:
    from .live.demo import run_demo

    return run_demo(minutes=a.minutes, runtime_dir=Path(a.runtime), show_experimental=a.experimental,
                    planted_edge=a.planted_edge, verbose=not a.quiet)


def cmd_train(a) -> int:
    from .signals.registry import train_bundle

    p = train_bundle(a.symbol, a.horizon, a.model, Path(a.root), Path(a.models), Path(a.frozen), a.months,
                     source=a.source)
    print(f"Modelo guardado: {p}")
    return 0


def cmd_live(a) -> int:
    from .live.runner import run_live

    return run_live(symbol=a.symbol, horizon=a.horizon, feed_name=a.feed, models_dir=Path(a.models),
                    runtime_dir=Path(a.runtime), iterations=a.iterations, model=a.model)


def cmd_research_study3(a) -> int:
    from .research import study3

    root = Path(a.root)
    if a.download:
        study3.download(root)
    rep = study3.run(root, Path(a.out), n_boot=a.n_boot)
    for s, v in rep["veredicto"].items():
        m = rep["resultados"][s]["modelos"]
        print(f"{s}: pasa={v['pasa']} | criterios {v} | referencia {m['referencia_precio']['hit']} "
              f"vs prueba {m['precio_mas_bloque_nuevo']['hit']}")
    return 0


def cmd_replay(a) -> int:
    from .live.replay import run_replay

    return run_replay(a.symbol, a.horizon, a.model, _d(a.start), _d(a.end), Path(a.runtime),
                      models_dir=Path(a.models), data_root=Path(a.root), entry_delay_s=a.entry_delay_s)


def _quantiles(values: list) -> dict | None:
    import numpy as np

    v = np.array([x for x in values if x is not None], float)
    if not len(v):
        return None
    return {"n": int(len(v)), "min": float(v.min()), "p5": float(np.percentile(v, 5)),
            "mediana": float(np.median(v)), "p95": float(np.percentile(v, 95)), "max": float(v.max())}


def cmd_live_verdict(a) -> int:
    import pandas as pd

    from . import jsonutil
    from .execution.paper import read_rows
    from .live.runner import LIVE_METHOD, EventLog
    from .research.metrics import wilson
    from .signals.monitor import fixed_sample, live_verdict
    from .signals.registry import load_observation

    # Aclaración 2: el entrenamiento, la política, la muestra y el plazo salen del REGISTRO, no del .env ni
    # de opciones elegidas después de ver datos.
    obs = load_observation(Path(a.observation))
    if not obs:
        print(f"No existe {a.observation}: la observación en vivo debe registrarse antes de iniciarla.")
        return 2
    if (a.symbol.upper(), a.horizon, a.model) != (obs["symbol"], obs["horizon"], obs["model"]):
        print(f"La observación registrada es {obs['symbol']} h={obs['horizon']} {obs['model']}, no "
              f"{a.symbol.upper()} h={a.horizon} {a.model}.")
        return 2
    mid, pol, n_target, max_days = obs["model_id"], obs["policy"], obs["sample_n"], obs["max_days"]
    path = Path(a.runtime) / "paper_ledger.jsonl"
    if not path.exists():
        print(f"No hay alertas evaluadas en {path}. ¿Está corriendo «tbot live --runtime {a.runtime}»?")
        return 2
    rows, bad = read_rows(path)
    of_model = [r for r in rows if r.get("model_id") == mid]
    live = [r for r in of_model if r.get("method") == LIVE_METHOD]
    sel = sorted((r for r in live if r.get("policy") == pol), key=lambda r: str(r.get("time", "")))
    # Una vela de decisión cuenta una sola vez (la primera alerta que la usó).
    seen, dedup, dups = set(), [], 0
    for r in sel:
        key = r.get("decision_time")
        if key is not None and key in seen:
            dups += 1
            continue
        seen.add(key)
        dedup.append(r)
    sample = fixed_sample(dedup, n_target)
    be = 1 / (1 + pol["payout"])  # p* del contrato registrado (binaria, empate reembolsado)
    v = live_verdict(sample, be, obs["symbol"], obs["model"], n_target)
    # Plazo máximo: la muestra debe completarse en `max_days` desde la primera alerta evaluada.
    times = [r["time"] for r in sample if r.get("time")]
    if times:
        t0, t_last = pd.Timestamp(times[0]), pd.Timestamp(times[-1])
        limit = t0 + pd.Timedelta(days=max_days)
        complete = v["n"] >= n_target
        if complete and t_last > limit:
            v["passed"] = False
            v["reasons"].append(f"no concluyente: la muestra se completó después de {max_days} días")
        elif not complete and pd.Timestamp.now(tz="UTC") > limit:
            v["reasons"].append(f"no concluyente: pasaron {max_days} días sin completar la muestra")
        v.update({"inicio": t0.isoformat(), "plazo_max": limit.isoformat()})
    # Secundario (no decide): solo las alertas que además pasaban el filtro de acierto histórico del grupo.
    sub = [r for r in sample if r.get("ic_filter_ok") and not r.get("tie")]
    sub_wins = sum(1 for r in sub if r.get("win"))
    sub_lo, _ = wilson(sub_wins, len(sub)) if sub else (None, None)
    by_hour: dict = {}
    for r in sample:
        if r.get("tie") or r.get("hora_bogota") is None:
            continue
        h = by_hour.setdefault(int(r["hora_bogota"]), {"n": 0, "aciertos": 0})
        h["n"] += 1
        h["aciertos"] += 1 if r.get("win") else 0
    q_ties = sum(1 for r in sample if r.get("tie")) / len(sample) if sample else 0.0
    v.update({"horizon": obs["horizon"], "model_id": mid, "policy": pol, "payout": pol["payout"],
              "tie_rule": pol["tie_rule"], "muestra_fija": True, "n_objetivo": n_target,
              "alertas_registradas": len(sel), "empates_observados": q_ties,
              "secundario_filtro_ic": {"n": len(sub), "aciertos": sub_wins,
                                       "acierto": sub_wins / len(sub) if sub else None, "hit_lo95": sub_lo},
              # Lo que la Aclaración 2 (punto 7) exige reportar siempre.
              "medicion": {"duracion_real_s": _quantiles([r.get("duracion_real_s") for r in sample]),
                           "retraso_vencimiento_s": _quantiles([r.get("retraso_s") for r in sample]),
                           "entrada_tras_cierre_s": _quantiles([r.get("entrada_tras_cierre_s") for r in sample]),
                           "desfase_reloj_s": _quantiles([r.get("desfase_reloj_s") for r in sample]),
                           "por_hora_bogota": dict(sorted(by_hour.items()))},
              "excluidas": {"de_otro_modelo_o_sin_modelo": len(rows) - len(of_model),
                            "evaluadas_con_velas": len(of_model) - len(live),
                            "politica_distinta_a_la_registrada": len(live) - len(sel),
                            "vela_de_decision_repetida": dups, "lineas_danadas": bad},
              # Alertas generadas que nunca llegaron al libro (sin precio, duración fuera de rango, reinicio…).
              "no_evaluables": EventLog(Path(a.runtime)).no_evaluable_summary(mid)})
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(jsonutil.dumps(v, indent=2), encoding="utf-8")
    print(jsonutil.dumps(v, indent=2))
    return 0


def cmd_serve(a) -> int:
    from .app.server import serve

    return serve(host=a.host, port=a.port, runtime_dir=Path(a.runtime), results_dir=Path(a.results))


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="tbot", description="Investigación y alertas con validación honesta.")
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("data", help="adquisición y calidad de datos").add_subparsers(dest="sub", required=True)
    x = d.add_parser("download", help="descarga Dukascopy/Binance al almacén local")
    x.add_argument("--symbols", required=True)
    x.add_argument("--start", default="2021-01-01")
    x.add_argument("--end", default="2026-09-01")
    x.add_argument("--root", default="data/raw")
    x.add_argument("--workers", type=int, default=8)
    x.add_argument("--source", choices=["dukascopy", "binance", "histdata"], default=None,
                   help="por defecto, la fuente del instrumento (Dukascopy para FX/oro, Binance para BTC)")
    x.set_defaults(func=cmd_data_download)
    x = d.add_parser("synth", help="genera datos SINTÉTICOS (solo pruebas/demostración)")
    x.add_argument("--start", default="2023-01-02")
    x.add_argument("--days", type=int, default=120)
    x.add_argument("--phi", type=float, default=0.0)
    x.add_argument("--seed", type=int, default=7)
    x.add_argument("--root", default="data/raw")
    x.set_defaults(func=cmd_data_synth)
    x = d.add_parser("import-histdata", help="importa un ZIP/CSV de HistData (BID, EST fija)")
    x.add_argument("--symbol", required=True)
    x.add_argument("--path", required=True)
    x.add_argument("--spread-pips", type=float, required=True)
    x.add_argument("--root", default="data/raw")
    x.set_defaults(func=cmd_data_import_histdata)
    x = d.add_parser("probe", help="diagnostica el acceso a las fuentes de datos desde esta máquina")
    x.add_argument("--pause", type=float, default=1.5)
    x.set_defaults(func=cmd_data_probe)
    x = d.add_parser("quality", help="informe de calidad de datos")
    x.add_argument("--symbol", required=True)
    x.add_argument("--root", default="data/raw")
    x.add_argument("--source", choices=["dukascopy", "binance", "histdata"], default=None)
    x.set_defaults(func=cmd_data_quality)

    r = sub.add_parser("research", help="estudio walk-forward").add_subparsers(dest="sub", required=True)
    x = r.add_parser("run")
    x.add_argument("--symbol", required=True)
    x.add_argument("--stage", choices=["dev", "holdout"], default="dev")
    x.add_argument("--config", default="config/research.toml")
    x.add_argument("--frozen", default="config/frozen.json")
    x.add_argument("--root", default="data/raw")
    x.add_argument("--out", default="results")
    x.add_argument("--n-boot", type=int, default=1000)
    x.add_argument("--source", choices=["dukascopy", "binance", "histdata"], default=None)
    x.set_defaults(func=cmd_research_run)
    x = r.add_parser("study3", help="Estudio 3, fase de desarrollo (pre-registro en docs/01)")
    x.add_argument("--root", default="data/raw/estudio3")
    x.add_argument("--out", default="results/estudio3")
    x.add_argument("--download", action="store_true", help="descarga antes los archivos de Binance")
    x.add_argument("--n-boot", type=int, default=1000)
    x.set_defaults(func=cmd_research_study3)
    x = r.add_parser("report")
    x.add_argument("--stage", choices=["dev", "holdout"], default="dev")
    x.add_argument("--config", default="config/research.toml")
    x.add_argument("--frozen", default="config/frozen.json")
    x.add_argument("--out", default="results")
    x.add_argument("--print", action="store_true")
    x.set_defaults(func=cmd_research_report)

    al = sub.add_parser("alerts", help="alertas").add_subparsers(dest="sub", required=True)
    x = al.add_parser("example", help="muestra el formato con un EJEMPLO FICTICIO")
    x.set_defaults(func=cmd_alerts_example)
    x = al.add_parser("demo", help="demostración reproducible con datos sintéticos")
    x.add_argument("--minutes", type=int, default=240)
    x.add_argument("--runtime", default="runtime/demo")
    x.add_argument("--experimental", action="store_true", help="mostrar señales experimentales (NO OPERAR)")
    x.add_argument("--planted-edge", action="store_true",
                   help="serie sintética con ventaja SEMBRADA (solo para ver el formato de una alerta)")
    x.add_argument("--quiet", action="store_true", help="alertas en una sola línea")
    x.set_defaults(func=cmd_alerts_demo)

    x = sub.add_parser("train", help="entrena un modelo para alertas en vivo")
    x.add_argument("--symbol", required=True)
    x.add_argument("--horizon", type=int, default=1)
    x.add_argument("--model", choices=["logit", "gbm"], default="logit")
    x.add_argument("--months", type=int, default=12)
    x.add_argument("--root", default="data/raw")
    x.add_argument("--models", default="models")
    x.add_argument("--frozen", default="config/frozen.json")
    x.add_argument("--source", choices=["dukascopy", "binance", "histdata", "synthetic"], default=None)
    x.set_defaults(func=cmd_train)

    x = sub.add_parser("live", help="alertas en vivo SIMULADAS (sin dinero real)")
    x.add_argument("--symbol", required=True)
    x.add_argument("--horizon", type=int, default=1)
    x.add_argument("--feed", choices=["binance"], default="binance")
    x.add_argument("--model", choices=["logit", "gbm"], default=None,
                   help="modelo a usar (obligatorio si hay varios entrenados para el símbolo y horizonte)")
    x.add_argument("--models", default="models")
    x.add_argument("--runtime", default="runtime/live")
    x.add_argument("--iterations", type=int, default=0, help="0 = sin límite")
    x.set_defaults(func=cmd_live)

    x = sub.add_parser("replay", help="reproduce el bucle en vivo con datos históricos de 1 s (Enmienda 2)")
    x.add_argument("--symbol", required=True)
    x.add_argument("--horizon", type=int, default=1)
    x.add_argument("--model", choices=["logit", "gbm"], required=True)
    x.add_argument("--start", required=True, help="primer día (UTC), p. ej. 2026-09-01")
    x.add_argument("--end", required=True, help="día final, excluido")
    x.add_argument("--runtime", required=True, help="carpeta vacía para el libro y los eventos")
    x.add_argument("--entry-delay-s", type=float, default=2.0,
                   help="segundos tras el cierre de la vela hasta el precio de entrada (registrado: 2)")
    x.add_argument("--models", default="models")
    x.add_argument("--root", default="data/raw")
    x.set_defaults(func=cmd_replay)

    x = sub.add_parser("live-verdict", help="veredicto de la observación en vivo sin dinero (criterios fijos)")
    x.add_argument("--symbol", required=True)
    x.add_argument("--horizon", type=int, default=1)
    x.add_argument("--model", choices=["logit", "gbm"], required=True)
    x.add_argument("--observation", default="config/observacion_en_vivo.json",
                   help="registro de la observación (entrenamiento, política, muestra y plazo)")
    # Sin opciones para cambiar el entrenamiento, la muestra ni el umbral: son fijos (Aclaración 2).
    x.add_argument("--runtime", default="runtime/live")
    x.add_argument("--out", default="results/live/verdict.json")
    x.set_defaults(func=cmd_live_verdict)

    x = sub.add_parser("serve", help="panel web local")
    x.add_argument("--host", default="127.0.0.1")
    x.add_argument("--port", type=int, default=8765)
    x.add_argument("--runtime", default="runtime/demo")
    x.add_argument("--results", default="results")
    x.set_defaults(func=cmd_serve)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args) or 0)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
