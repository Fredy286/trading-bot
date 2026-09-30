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
        store.ensure_downloaded(inst, _d(a.start), _d(a.end), Path(a.root), workers=a.workers)
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


def cmd_data_quality(a) -> int:
    from .data import store
    from .data.clean import to_canonical
    from .instruments import get_instrument

    inst = get_instrument(a.symbol)
    _, rep = to_canonical(store.load(Path(a.root), inst))
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
    raw = store.load(Path(a.root), inst)
    res = run_symbol(inst.symbol, raw, a.stage, cfg, n_boot=a.n_boot)
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

    return run_demo(minutes=a.minutes, runtime_dir=Path(a.runtime), show_experimental=a.experimental)


def cmd_train(a) -> int:
    from .signals.registry import train_bundle

    p = train_bundle(a.symbol, a.horizon, a.model, Path(a.root), Path(a.models), Path(a.frozen), a.months)
    print(f"Modelo guardado: {p}")
    return 0


def cmd_live(a) -> int:
    from .live.runner import run_live

    return run_live(symbol=a.symbol, horizon=a.horizon, feed_name=a.feed, models_dir=Path(a.models),
                    runtime_dir=Path(a.runtime), iterations=a.iterations)


def cmd_serve(a) -> int:
    from .app.server import serve

    serve(host=a.host, port=a.port, runtime_dir=Path(a.runtime), results_dir=Path(a.results))
    return 0


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
    x = d.add_parser("quality", help="informe de calidad de datos")
    x.add_argument("--symbol", required=True)
    x.add_argument("--root", default="data/raw")
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
    x.set_defaults(func=cmd_research_run)
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
    x.set_defaults(func=cmd_alerts_demo)

    x = sub.add_parser("train", help="entrena un modelo para alertas en vivo")
    x.add_argument("--symbol", required=True)
    x.add_argument("--horizon", type=int, default=1)
    x.add_argument("--model", choices=["logit", "gbm"], default="logit")
    x.add_argument("--months", type=int, default=12)
    x.add_argument("--root", default="data/raw")
    x.add_argument("--models", default="models")
    x.add_argument("--frozen", default="config/frozen.json")
    x.set_defaults(func=cmd_train)

    x = sub.add_parser("live", help="alertas en vivo SIMULADAS (sin dinero real)")
    x.add_argument("--symbol", required=True)
    x.add_argument("--horizon", type=int, default=1)
    x.add_argument("--feed", choices=["binance"], default="binance")
    x.add_argument("--models", default="models")
    x.add_argument("--runtime", default="runtime/live")
    x.add_argument("--iterations", type=int, default=0, help="0 = sin límite")
    x.set_defaults(func=cmd_live)

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
