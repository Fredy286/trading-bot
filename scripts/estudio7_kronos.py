"""Estudio 7 (pre-registro 1492079): predicciones de Kronos-small, sin reentrenar, en los minutos del conjunto E.

Corre en el entorno de Kronos (torch), NO en el del proyecto:
  ~/proyectos/kronos-externo/.venv/bin/python -I scripts/estudio7_kronos.py --kronos ~/proyectos/kronos-externo

Para cada minuto t de `data/processed/estudio7/E.parquet` usa las 512 velas de 1 min t−511 … t (contado de Binance,
`data/raw/estudio3/BTCUSDT/spot`), predice 1 vela con T = 0,6, top-p = 0,9 y 5 muestras promediadas, y guarda
`ln(cierre predicho de t+1 / cierre reconstruido de t)`, ambos del mismo decodificado. Avanza por bloques de 512
minutos con su propio archivo: si se interrumpe, al relanzarlo continúa donde quedó.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
CTX, T, TOP_P, SAMPLES, SEED, BATCH, BLOCK = 512, 0.6, 0.9, 5, 20261025, 64, 512
MODEL, TOKENIZER = "NeoQuasar/Kronos-small", "NeoQuasar/Kronos-Tokenizer-base"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--kronos", required=True, help="carpeta del repositorio de Kronos (commit 67b630e)")
    ap.add_argument("--threads", type=int, default=10)
    ap.add_argument("--work", default=str(RAIZ / "data/processed/estudio7"), help="carpeta con E.parquet")
    a = ap.parse_args()
    sys.path.insert(0, str(Path(a.kronos).expanduser()))
    import torch
    from huggingface_hub import HfApi
    from model import Kronos, KronosTokenizer
    from model.kronos import auto_regressive_inference, calc_time_stamps

    torch.set_num_threads(a.threads)
    work = Path(a.work)
    parts = work / "kronos_bloques"
    parts.mkdir(parents=True, exist_ok=True)
    e = pd.read_parquet(work / "E.parquet")["time"].sort_values().reset_index(drop=True)
    spot = pd.concat(pd.read_parquet(f) for f in sorted((RAIZ / "data/raw/estudio3/BTCUSDT/spot").glob("*.parquet")))
    spot = spot[~spot.index.duplicated(keep="last")].sort_index()
    spot = spot[(spot.index >= e.min() - pd.Timedelta(days=2)) & (spot.index <= e.max() + pd.Timedelta(minutes=1))]
    grid = pd.date_range(spot.index[0], spot.index[-1], freq="min")
    spot = spot.reindex(grid)
    x_all = pd.DataFrame({"open": spot["o"], "high": spot["h"], "low": spot["l"], "close": spot["c"],
                          "volume": spot["volume"]})
    x_all["amount"] = x_all["volume"] * x_all[["open", "high", "low", "close"]].mean(axis=1)  # como el código oficial
    vals = x_all.to_numpy(np.float32)
    stamps = calc_time_stamps(pd.Series(grid)).to_numpy(np.float32)
    pos_of = pd.Series(np.arange(len(grid)), index=grid)
    tok = KronosTokenizer.from_pretrained(TOKENIZER).eval()
    model = Kronos.from_pretrained(MODEL).eval()
    api = HfApi()
    revs = {r: api.model_info(r).sha for r in (MODEL, TOKENIZER)}
    print(f"Modelos: {revs}", flush=True)
    t0 = time.time()
    for b0 in range(0, len(e), BLOCK):
        f = parts / f"bloque_{b0 // BLOCK:03d}.parquet"
        if f.exists():
            continue
        times = e.iloc[b0:b0 + BLOCK]
        rows = []
        for c0 in range(0, len(times), BATCH):
            tt = times.iloc[c0:c0 + BATCH]
            pos = pos_of[pd.DatetimeIndex(tt)].to_numpy()
            xs, mus, sds, xst, yst = [], [], [], [], []
            for p in pos:
                w = vals[p - CTX + 1:p + 1]
                if len(w) != CTX or np.isnan(w).any():
                    raise RuntimeError(f"Contexto incompleto en {grid[p]} (E debía excluirlo).")
                mu, sd = w.mean(0), w.std(0)
                xs.append(np.clip((w - mu) / (sd + 1e-5), -5, 5))
                mus.append(mu)
                sds.append(sd)
                xst.append(stamps[p - CTX + 1:p + 1])
                yst.append(stamps[p + 1:p + 2])
            torch.manual_seed(SEED + b0 + c0)
            z = auto_regressive_inference(tok, model, torch.from_numpy(np.stack(xs)), torch.from_numpy(np.stack(xst)),
                                          torch.from_numpy(np.stack(yst)), CTX, 1, 5, T, 0, TOP_P, SAMPLES)
            mu, sd = np.stack(mus), np.stack(sds)
            close = z[:, :, 3] * (sd[:, 3:4] + 1e-5) + mu[:, 3:4]  # columna 3 = cierre
            recon, pred = close[:, -2], close[:, -1]
            for i, ti in enumerate(tt):
                rows.append({"time": ti, "kronos_pred": float(pred[i]), "kronos_recon": float(recon[i]),
                             "kronos_lr": float(np.log(pred[i] / recon[i]))})
        pd.DataFrame(rows).to_parquet(f)
        done = min(b0 + BLOCK, len(e))
        el = time.time() - t0
        print(f"{done:,}/{len(e):,} minutos  ({el / 60:.1f} min)", flush=True)
    out = pd.concat(pd.read_parquet(f) for f in sorted(parts.glob("bloque_*.parquet")))
    out["modelo"], out["modelo_rev"], out["tokenizador_rev"] = MODEL, revs[MODEL], revs[TOKENIZER]
    out.sort_values("time").to_parquet(work / "kronos.parquet")
    print(f"Listo: {len(out):,} predicciones → {work / 'kronos.parquet'}", flush=True)


if __name__ == "__main__":
    main()
