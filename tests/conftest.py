"""Utilidades compartidas por las pruebas. Todos los datos aquí son SINTÉTICOS."""

import numpy as np
import pandas as pd
import pytest

from tradingbot.data import synthetic
from tradingbot.data.clean import to_canonical


def make_bars(closes, spread=0.0002, start="2024-01-02 10:00", point=1e-5, no_tick=None):
    """Velas canónicas simples: apertura = cierre anterior, spread constante."""
    closes = np.asarray(closes, float)
    idx = pd.date_range(pd.Timestamp(start, tz="UTC"), periods=len(closes), freq="min", name="time")
    opens = np.concatenate(([closes[0]], closes[:-1]))
    df = pd.DataFrame({"o": opens, "h": np.maximum(opens, closes), "l": np.minimum(opens, closes), "c": closes},
                      index=idx)
    df["spread_o"] = spread
    df["spread_c"] = spread
    df["volume"] = 1.0
    df["no_tick"] = False if no_tick is None else no_tick
    return df


@pytest.fixture(scope="session")
def synth_raw():
    return synthetic.generate(start="2023-01-02", days=20, phi=0.0, seed=3)


@pytest.fixture(scope="session")
def synth_bars(synth_raw):
    bars, _ = to_canonical(synth_raw)
    return bars
