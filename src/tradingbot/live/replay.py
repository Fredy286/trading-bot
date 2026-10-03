"""Reproducción del bucle en vivo con datos históricos de Binance (Enmienda 2 del protocolo).

En lugar de dejar un equipo encendido semanas, se recorre minuto a minuto un periodo que el modelo no
vio, con el MISMO código que en vivo (`SignalEngine` + `AlertLoop`, política registrada):
- decisión 1 s después del cierre de cada vela de 1 minuto, con las velas ya publicadas;
- precio de entrada = último negociado antes de cierre + `entry_delay_s` (vela de 1 s que termina ahí);
- vencimiento = el mismo criterio 60 s después.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from ..config import Settings
from ..instruments import get_instrument
from ..signals.engine import SignalEngine
from .feeds import ReplayFeed
from .runner import AlertLoop

CYCLE_OFFSET_S = 1.0  # el ciclo corre 1 s después del cierre (config/observacion_en_vivo.json)
PUBLISH_LATENCY_S = 0.3  # Binance publica la vela cerrada ~0,3 s después del cierre (medido 2026-10-03)


class HistoricalPriceFeed(ReplayFeed):
    """Velas de 1 minuto visibles según su hora de publicación y precio «en vivo» de las velas de 1 s."""

    def __init__(self, bars: pd.DataFrame, closes_1s: pd.Series, entry_delay_s: float = 2.0,
                 max_gap_s: int = 5):
        super().__init__(bars, feed_latency_s=PUBLISH_LATENCY_S)
        self._open_ns = bars.index.asi8 if bars.index.unit == "ns" else bars.index.as_unit("ns").asi8
        idx = closes_1s.index if closes_1s.index.unit == "ns" else closes_1s.index.as_unit("ns")
        self._sec = idx.asi8 // 10**9  # segundo de apertura de cada vela de 1 s
        self._px = closes_1s.to_numpy(float)
        # Vela de 1 s cuyo cierre es el último precio antes de (cierre de la vela de 1 min + entry_delay_s).
        self.shift_s = int(round(entry_delay_s - CYCLE_OFFSET_S - 1))
        self.max_gap_s = max_gap_s

    def get(self, now_utc: datetime, lookback: int = 2000) -> tuple[pd.DataFrame, datetime]:
        cutoff = pd.Timestamp(now_utc) - self.latency - pd.Timedelta(minutes=1)
        pos = int(np.searchsorted(self._open_ns, cutoff.value, side="right"))
        return self.bars.iloc[max(0, pos - lookback):pos], now_utc

    def current_price(self, now_utc: datetime) -> tuple[float, datetime]:
        target = int(pd.Timestamp(now_utc).floor("s").value // 10**9) + self.shift_s
        i = int(np.searchsorted(self._sec, target, side="right")) - 1
        if i < 0 or target - self._sec[i] > self.max_gap_s:
            raise ValueError(f"sin operaciones en los {self.max_gap_s} s anteriores a {pd.Timestamp(target, unit='s')}")
        # Hora del precio = fin de la vela de 1 s objetivo (último negociado antes de ese instante).
        return float(self._px[i]), (pd.Timestamp(target + 1, unit="s", tz="UTC")).to_pydatetime()


def delay_sensitivity(rows: list[dict], closes_1s: pd.Series, delays=(1, 2, 3, 5, 10, 30),
                      payouts=(0.85, 0.80), point: float = 0.01, max_gap_s: int = 5) -> list[dict]:
    """Sensibilidad informativa (Enmienda 2): las MISMAS alertas, con entrada a +d s del cierre de la
    vela y vencimiento 60 s después, medidas con las velas de 1 s. No decide nada."""
    from ..research.metrics import wilson

    idx = closes_1s.index if closes_1s.index.unit == "ns" else closes_1s.index.as_unit("ns")
    sec, px = idx.asi8 // 10**9, closes_1s.to_numpy(float)

    def price_before(t: int) -> float | None:  # último negociado antes del segundo t
        i = int(np.searchsorted(sec, t - 1, side="right")) - 1
        return float(px[i]) if i >= 0 and (t - 1) - sec[i] <= max_gap_s else None

    out = []
    for d in delays:
        wins = losses = ties = missing = 0
        for r in rows:
            t0 = int(pd.Timestamp(r["decision_time"]).value // 10**9)
            o, c = price_before(t0 + d), price_before(t0 + d + 60)
            if o is None or c is None:
                missing += 1
                continue
            mv = np.sign(round((c - o) / (point / 2)))
            side = 1 if r["direction"] == "sube" else -1
            ties += mv == 0
            wins += mv == side
            losses += mv == -side
        n = wins + losses
        lo, _ = wilson(wins, n) if n else (float("nan"), float("nan"))
        for b in payouts:
            out.append({"entrada_s": d, "pago": b, "n": n, "aciertos": wins, "empates": ties, "sin_precio": missing,
                        "acierto": wins / n if n else None, "lo95": lo, "umbral": 1 / (1 + b),
                        "ev": (wins * b - losses) / (n + ties) if n + ties else None})
    return out


def run_replay(symbol: str, horizon: int, model: str, start: date, end: date, runtime_dir: Path,
               models_dir: Path = Path("models"), data_root: Path = Path("data/raw"),
               entry_delay_s: float = 2.0, observation_path: Path | None = None, progress: bool = True) -> int:
    from ..data import store
    from ..data.binance import download_days
    from ..data.clean import to_canonical
    from ..signals.registry import OBSERVED, ModelBundle, apply_policy, load_observation

    runtime_dir = Path(runtime_dir)
    if runtime_dir.exists() and any(runtime_dir.iterdir()):
        print(f"{runtime_dir} ya tiene datos: use una carpeta vacía para no mezclar reproducciones.")
        return 2
    inst = get_instrument(symbol)
    p = Path(models_dir) / f"{inst.symbol}_h{horizon}_{model}.pkl"
    if not p.exists():
        print(f"No existe {p}.")
        return 2
    bundle = ModelBundle.load(p)
    s = Settings()
    if bundle.validation_status in OBSERVED:
        obs = load_observation(observation_path) if observation_path else load_observation()
        if not obs or obs.get("model_id") != bundle.model_id:
            print(f"El modelo {bundle.model_id} no es el registrado ({(obs or {}).get('model_id')}).")
            return 2
        apply_policy(s, obs["policy"])
    # Velas de 1 min: historia previa (calentamiento de variables) + archivos diarios del periodo.
    hist = store.load(Path(data_root), inst, source="binance")
    hist = hist[hist.index >= pd.Timestamp(start, tz="UTC") - pd.Timedelta(days=3)]
    daily_cache = Path(data_root) / "binance_daily"
    new = download_days(inst, start, end + timedelta(days=1), "1m", cache_dir=daily_cache, progress=progress)
    raw = pd.concat([hist, new]).sort_index()
    raw = raw[~raw.index.duplicated(keep="last")]
    bars, _ = to_canonical(raw)
    closes = download_days(inst, start, end + timedelta(days=1), "1s", cache_dir=daily_cache, progress=progress)
    feed = HistoricalPriceFeed(bars, closes, entry_delay_s=entry_delay_s)
    engine = SignalEngine(bundle, s, inst, price_source="Binance spot (reproducción con velas de 1 s)")
    first_now = pd.Timestamp(start, tz="UTC") + pd.Timedelta(minutes=1, seconds=CYCLE_OFFSET_S)
    loop = AlertLoop(engine, feed, [], runtime_dir, s, clock=lambda: first_now.to_pydatetime())
    loop.state_every = 1440  # estado del panel una vez por día simulado (no cambia ninguna medición)
    loop.log.write("started", model_id=bundle.model_id, validation_status=bundle.validation_status,
                   modo="reproducción histórica (Enmienda 2)", entry_delay_s=entry_delay_s,
                   inicio=str(start), fin=str(end))
    t = first_now
    stop = pd.Timestamp(end, tz="UTC") + pd.Timedelta(minutes=2)  # deja vencer la última alerta
    day = None
    while t <= stop:
        loop.step(t.to_pydatetime())
        if progress and t.date() != day:
            day = t.date()
            print(f"  {day}: {loop.status_counts}", flush=True)
        t += pd.Timedelta(minutes=1)
    loop.write_state()
    loop.log.write("stopped", motivo="fin de la reproducción")
    print(f"Reproducción terminada: {loop.status_counts}; alertas evaluadas: {len(loop.ledger.trades)}")
    return 0
