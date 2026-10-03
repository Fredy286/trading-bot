"""Paquetes de modelo para alertas en vivo, con su estado de validación explícito.

Estados (de menor a mayor confianza):
  NO_VALIDADO        la configuración no superó los criterios del estudio → «SIN SEÑAL»
                     (o «EXPERIMENTAL — NO OPERAR» si el usuario lo pide expresamente)
  CANDIDATO_DEV      superó el walk-forward de desarrollo → solo EXPERIMENTAL
  VALIDADO_HOLDOUT   superó además el periodo bloqueado → EN OBSERVACIÓN (experimental en vivo)
  VALIDADO           superó además la observación en vivo sin dinero → puede emitir «SEÑAL»
El estado se deriva de archivos de resultados, no se escribe a mano.
"""

from __future__ import annotations

import hashlib
import json
import pickle
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from .. import __version__
from ..data import store
from ..data.clean import to_canonical
from ..instruments import get_instrument
from ..research.calibration import Calibrator
from ..research.features import FEATURES, compute_features
from ..research.labels import decision_mask, make_labels
from ..research.models import fit_predict_proba
from .monitor import LIVE_SAMPLE_N
from ..timeutil import utcnow

ACTIONABLE = {"VALIDADO"}
OBSERVED = {"VALIDADO_HOLDOUT"}  # en observación en vivo: sus alertas se registran siempre como EXPERIMENTAL
STATUS_ORDER = ["NO_VALIDADO", "CANDIDATO_DEV", "VALIDADO_HOLDOUT", "VALIDADO"]


@dataclass
class ModelBundle:
    symbol: str
    horizon: int
    model_name: str
    model: object
    calibrator: Calibrator
    features: list[str]
    trained_from: str
    trained_to: str
    source: str
    validation_status: str = "NO_VALIDADO"
    validation_evidence: dict = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: utcnow().isoformat())
    code_version: str = __version__
    synthetic: bool = False
    # Huella del entrenamiento (datos usados + predicciones de calibración): dos modelos distintos cuyos
    # datos terminan el mismo día no comparten identificador; uno idéntico, sí.
    fingerprint: str = ""

    @property
    def model_id(self) -> str:
        fp = getattr(self, "fingerprint", "")  # modelos guardados antes de existir este campo
        return f"{self.symbol}-h{self.horizon}-{self.model_name}-{self.trained_to[:10]}" + (f"-{fp}" if fp else "")

    def predict_p_up(self, X: pd.DataFrame) -> np.ndarray:
        raw = self.model.predict_proba(X[self.features].to_numpy())[:, 1]
        return self.calibrator.transform(raw)

    def save(self, models_dir: Path) -> Path:
        models_dir = Path(models_dir)
        models_dir.mkdir(parents=True, exist_ok=True)
        p = models_dir / f"{self.symbol}_h{self.horizon}_{self.model_name}.pkl"
        with open(p, "wb") as fh:
            pickle.dump(self, fh)
        meta = {k: v for k, v in self.__dict__.items() if k not in ("model", "calibrator")}
        p.with_suffix(".json").write_text(json.dumps(meta, indent=2, ensure_ascii=False, default=str))
        return p

    @staticmethod
    def load(path: Path) -> "ModelBundle":
        # Solo cargar archivos creados por este mismo programa (pickle ejecuta código al cargar).
        with open(path, "rb") as fh:
            return pickle.load(fh)


def validation_status_for(symbol: str, horizon: int, model: str, frozen_path: Path,
                          holdout_verdict_path: Path | None = None,
                          live_verdict_path: Path | None = None) -> tuple[str, dict]:
    """Deriva el estado de validación a partir de los archivos generados por el estudio."""
    evidence: dict = {}
    frozen_path = Path(frozen_path)
    if not frozen_path.exists():
        return "NO_VALIDADO", {"motivo": "no existe config/frozen.json (no se ha corrido el estudio)"}
    fz = json.loads(frozen_path.read_text(encoding="utf-8"))
    match = [c for c in fz.get("candidates", []) if c["symbol"] == symbol and int(c["horizon"]) == horizon
             and c["model"] == model]
    evidence["dev"] = match or f"sin candidatas para {symbol} h={horizon} {model} (veredicto: {fz.get('verdict')})"
    if not match:
        return "NO_VALIDADO", evidence
    status = "CANDIDATO_DEV"
    if holdout_verdict_path and Path(holdout_verdict_path).exists():
        hv = json.loads(Path(holdout_verdict_path).read_text(encoding="utf-8"))
        # Solo cuenta el periodo bloqueado del MISMO estudio que congeló config/frozen.json.
        same = (hv.get("frozen_git_sha") == fz.get("git_sha") and hv.get("config_hash") == fz.get("config_hash"))
        ok = same and any(c["symbol"] == symbol and int(c["horizon"]) == horizon and c["model"] == model
                          for c in hv.get("passed", []))
        evidence["holdout"] = hv if same else "results/holdout es de otro estudio (no coincide con config/frozen.json)"
        if ok:
            status = "VALIDADO_HOLDOUT"
            if live_verdict_path and Path(live_verdict_path).exists():
                lv = json.loads(Path(live_verdict_path).read_text(encoding="utf-8"))
                evidence["live"] = lv
                # Criterios fijos (Aclaración 2): muestra fija de LIVE_SAMPLE_N y umbral ≥ p* del contrato.
                p_star = 1 / (1 + (lv.get("payout") or 0.85))
                fixed = (lv.get("muestra_fija") is True and (lv.get("min_n") or 0) >= LIVE_SAMPLE_N
                         and (lv.get("breakeven") or 0) >= p_star - 1e-9)
                if (lv.get("passed") and fixed and lv.get("model") == model and lv.get("symbol") == symbol
                        and lv.get("horizon") == horizon):
                    status = "VALIDADO"
    return status, evidence


def fit_bundle(bars: pd.DataFrame, symbol: str, horizon: int, model_name: str, source: str,
               point: float, max_rows: int = 400_000, seed: int = 2024, synthetic: bool = False) -> ModelBundle:
    """Entrena con 80 % inicial y calibra con el 20 % final (con purga), como en el estudio."""
    feats = compute_features(bars)
    lab = make_labels(bars, horizon, 1, point)
    ok = decision_mask(bars.index, horizon) & feats.notna().all(axis=1).to_numpy() & \
        lab["dir"].notna().to_numpy() & (lab["dir"] != 0).to_numpy()
    X = feats[ok]
    y = (lab.loc[ok, "dir"] == 1).astype(int).to_numpy()
    le = pd.DatetimeIndex(lab.loc[ok, "label_end"])
    if len(X) < 2000:
        raise ValueError(f"Datos insuficientes para entrenar ({len(X)} decisiones válidas)")
    cut = X.index[int(len(X) * 0.8)]
    fit = (X.index < cut) & (le <= cut)
    cal = X.index >= cut
    model, (p_cal,) = fit_predict_proba(model_name, X[fit], y[fit], [X[cal]], seed=seed, max_rows=max_rows)
    calib = Calibrator().fit(p_cal, y[cal])
    trained_from, trained_to = str(X.index.min()), str(X.index.max())
    fp = hashlib.sha1(np.round(np.asarray(p_cal, float), 9).tobytes()
                      + f"{trained_from}|{trained_to}|{source}|{len(X)}|{model_name}".encode()).hexdigest()[:6]
    return ModelBundle(symbol=symbol, horizon=horizon, model_name=model_name, model=model, calibrator=calib,
                       features=list(FEATURES), trained_from=trained_from, trained_to=trained_to,
                       source=source, synthetic=synthetic, fingerprint=fp)


def train_bundle(symbol: str, horizon: int, model_name: str, root: Path, models_dir: Path, frozen_path: Path,
                 months: int = 12, source: str | None = None) -> Path:
    inst = get_instrument(symbol)
    source = source or inst.source
    raw = store.load(Path(root), inst, source=source)
    bars, _ = to_canonical(raw, fill_gaps=(source == "histdata"))
    start = bars.index.max() - pd.DateOffset(months=months)
    bars = bars[bars.index >= start]
    b = fit_bundle(bars, inst.symbol, horizon, model_name, source, inst.point,
                   synthetic=source == "synthetic")
    status, evidence = validation_status_for(inst.symbol, horizon, model_name, frozen_path,
                                             Path("results/holdout/verdict.json"), Path("results/live/verdict.json"))
    if b.synthetic:
        status, evidence = "NO_VALIDADO", {"motivo": "entrenado con datos SINTÉTICOS"}
    b.validation_status, b.validation_evidence = status, evidence
    return b.save(models_dir)
