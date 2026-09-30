"""Calibración isotónica de P(sube) y tabla de confiabilidad por bins de confianza.

El calibrador se ajusta en un tramo DISTINTO del usado para entrenar el modelo, y se evalúa en datos
no vistos. Para cada señal se puede obtener un intervalo de Wilson a partir del bin de confianza al
que pertenece (cuántas señales comparables hubo en calibración y cuántas acertaron).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from sklearn.isotonic import IsotonicRegression

from .metrics import wilson


@dataclass
class Calibrator:
    n_bins: int = 10
    iso: IsotonicRegression = field(default_factory=lambda: IsotonicRegression(
        y_min=0.0, y_max=1.0, out_of_bounds="clip", increasing=True))
    edges: np.ndarray | None = None
    bin_n: np.ndarray | None = None
    bin_hits: np.ndarray | None = None

    min_bin_size: int = 500

    def fit(self, raw_p_up: np.ndarray, y_up: np.ndarray) -> "Calibrator":
        """Isotónica sobre bins de cuantiles con ≥ `min_bin_size` observaciones cada uno.

        La isotónica directa asigna 0 o 1 a las colas con pocas muestras, justo donde una política
        selectiva operaría; agrupar antes evita esas probabilidades extremas espurias.
        """
        raw_p_up = np.asarray(raw_p_up, float)
        y_up = np.asarray(y_up, float)
        nb = int(np.clip(len(raw_p_up) // self.min_bin_size, 1, 200))
        edges = np.unique(np.quantile(raw_p_up, np.linspace(0, 1, nb + 1)))
        b = np.clip(np.searchsorted(edges, raw_p_up, side="right") - 1, 0, max(len(edges) - 2, 0))
        cnt = np.bincount(b)
        keep = cnt > 0
        xm = np.bincount(b, weights=raw_p_up)[keep] / cnt[keep]
        ym = np.bincount(b, weights=y_up)[keep] / cnt[keep]
        self.iso.fit(xm, ym, sample_weight=cnt[keep])
        p = self.iso.predict(raw_p_up)
        conf = np.maximum(p, 1 - p)
        correct = np.where(p >= 0.5, y_up, 1 - y_up)
        qs = np.quantile(conf, np.linspace(0, 1, self.n_bins + 1))
        qs[0], qs[-1] = 0.5, 1.0 + 1e-12
        self.edges = np.unique(qs)
        b = np.clip(np.searchsorted(self.edges, conf, side="right") - 1, 0, len(self.edges) - 2)
        k = len(self.edges) - 1
        self.bin_n = np.bincount(b, minlength=k)
        self.bin_hits = np.bincount(b, weights=correct, minlength=k)
        return self

    def transform(self, raw_p_up: np.ndarray) -> np.ndarray:
        return self.iso.predict(np.asarray(raw_p_up, float))

    def interval(self, conf: np.ndarray, z: float = 1.645) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Intervalo de Wilson (90 % por defecto) del acierto en el bin de calibración correspondiente."""
        conf = np.atleast_1d(np.asarray(conf, float))
        b = np.clip(np.searchsorted(self.edges, conf, side="right") - 1, 0, len(self.edges) - 2)
        n = self.bin_n[b]
        k = self.bin_hits[b]
        lo, hi = wilson(k, n, z=z)
        return lo, hi, n
