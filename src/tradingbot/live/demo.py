"""Demostración reproducible del sistema de alertas con datos SINTÉTICOS y reloj simulado.

No usa red ni dinero. Muestra el ciclo completo: entrenamiento → evaluación minuto a minuto →
«SIN SEÑAL» o alerta EXPERIMENTAL → notificación → evaluación al vencer → monitor de deterioro.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from ..config import Settings
from ..data import synthetic
from ..data.clean import to_canonical
from ..instruments import get_instrument
from ..notify import ConsoleNotifier, FileNotifier
from ..signals.alert import fictitious_example
from ..signals.registry import fit_bundle
from .feeds import ReplayFeed
from .runner import AlertLoop


def run_demo(minutes: int = 240, runtime_dir: Path = Path("runtime/demo"), show_experimental: bool = False,
             planted_edge: bool = False, verbose: bool = True) -> int:
    runtime_dir = Path(runtime_dir)
    runtime_dir.mkdir(parents=True, exist_ok=True)
    for f in ("events.jsonl", "paper_ledger.jsonl", "notifications.jsonl"):
        (runtime_dir / f).unlink(missing_ok=True)
    phi = -0.3 if planted_edge else 0.0
    print("=" * 72)
    print("DEMOSTRACIÓN CON DATOS SINTÉTICOS — nada de esto es una predicción de mercado real.")
    print(f"Serie: {'con ventaja SEMBRADA artificialmente (phi=-0.3)' if planted_edge else 'paseo aleatorio'}")
    print("Formato de ejemplo exigido:", fictitious_example())
    print("=" * 72)
    raw = synthetic.generate(start="2023-01-02", days=45, phi=phi, seed=21)
    bars, _ = to_canonical(raw)
    inst = get_instrument("SYNTH")
    train_end = pd.Timestamp("2023-02-06", tz="UTC")
    bundle = fit_bundle(bars[bars.index < train_end], "SYNTH", 1, "logit", "synthetic", inst.point,
                        synthetic=True)
    bundle.validation_status = "NO_VALIDADO"
    bundle.validation_evidence = {"motivo": "entrenado con datos SINTÉTICOS"}
    s = Settings(instruments=["SYNTH"], show_experimental=show_experimental, notify=["console", "file"],
                 broker="ninguno (demostración)", runtime_dir=str(runtime_dir), max_alerts_per_day=10_000,
                 max_daily_loss=1e9, max_consecutive_losses=10_000)
    from ..signals.engine import SignalEngine

    engine = SignalEngine(bundle, s, inst, price_source="SINTÉTICO (generador local)")
    feed = ReplayFeed(bars, feed_latency_s=s.feed_latency_s)
    notifiers = [ConsoleNotifier(verbose=verbose), FileNotifier(runtime_dir / "notifications.jsonl")]
    loop = AlertLoop(engine, feed, notifiers, runtime_dir, s)
    start = pd.Timestamp("2023-02-07 12:00", tz="UTC")
    for i in range(minutes):
        now = (start + pd.Timedelta(minutes=i, seconds=s.feed_latency_s + 1)).to_pydatetime()
        loop.step(now)
    counts = loop.status_counts
    print("=" * 72)
    print(f"Resumen de {minutes} minutos simulados: {counts}")
    print(f"Alertas evaluadas: {len(loop.outcomes)} | monitor: {loop.monitor.status} — {loop.monitor.detail}")
    shadow = [t for t in loop.ledger.trades if t["shadow"]]
    if shadow:
        pnl = sum(t["pnl"] for t in shadow)
        hits = sum(1 for t in shadow if t["win"])
        ties = sum(1 for t in shadow if t["tie"])
        n = len(shadow) - ties  # como el veredicto: los empates se reembolsan y no cuentan para el acierto
        rate = f" ({hits / n:.1%})" if n else ""
        print(f"Resultado hipotético de alertas experimentales (sin dinero): {hits}/{n} aciertos{rate} sin "
              f"contar {ties} empate{'s' if ties != 1 else ''}, PnL {pnl:+.2f} unidades de apuesta")
    print(f"Estado para el panel: {runtime_dir / 'state.json'}  →  tbot serve --runtime {runtime_dir}")
    return 0
