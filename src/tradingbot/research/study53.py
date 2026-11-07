"""Estudio 53 (pre-registro en docs/01): blitz de Solana de IQ Option (3 min desde la compra, pago 86 %) con la receta del
Estudio 42, igual que el Estudio 51 pero con SOL/USDT. Solana es, con Bitcoin, la única criptomoneda con blitz de precio
real en IQ Option (revisión del 2026-11-07); su duración, pago y precio se verifican cuando abra.
"""

from __future__ import annotations

from pathlib import Path

from . import study51

SYMBOL = "SOLUSDT"
TAB = Path("data/processed/estudio26/SOLUSDT/tabla.parquet")
M1 = Path("data/processed/estudio26/SOLUSDT/1m")


def run(out_dir: Path = Path("results/estudio53"), n_boot: int = 1000, log=print) -> dict:
    return study51.run(out_dir=out_dir, n_boot=n_boot, log=log, symbol=SYMBOL, tab_path=TAB, m1=M1, prefijo="H53",
                       estudio="Estudio 53 — blitz de Solana de IQ Option con la receta del Estudio 42 (pre-registro en docs/01)")
