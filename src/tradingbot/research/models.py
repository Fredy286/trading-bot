"""Modelos pre-registrados (hiperparámetros fijos; ver protocolo, sección 4).

Reglas de referencia → devuelven dirección (+1 sube, −1 baja, 0 no opera).
Modelos probabilísticos → devuelven P(sube) sin calibrar; la calibración es aparte.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from .features import FEATURES

RULES = ["random", "majority", "momentum1", "reversal1", "sma20_trend", "rsi14_extremes", "boll_reversal"]
PROB_MODELS = ["logit", "gbm"]


def rule_direction(name: str, X: pd.DataFrame, y_fit: np.ndarray | None = None, seed: int = 0) -> np.ndarray:
    n = len(X)
    if name == "random":
        return np.random.default_rng(seed).choice([-1.0, 1.0], size=n)
    if name == "majority":
        up = 1.0 if (y_fit is not None and np.mean(y_fit) >= 0.5) else -1.0
        return np.full(n, up)
    if name == "momentum1":
        return np.sign(X["r0"].to_numpy())
    if name == "reversal1":
        return -np.sign(X["r0"].to_numpy())
    if name == "sma20_trend":
        return np.sign(X["d_sma20"].to_numpy())
    if name == "rsi14_extremes":
        rsi = X["rsi14"].to_numpy() * 50 + 50
        return np.where(rsi < 30, 1.0, np.where(rsi > 70, -1.0, 0.0))
    if name == "boll_reversal":
        z = X["boll_z"].to_numpy()
        return np.where(z < -2, 1.0, np.where(z > 2, -1.0, 0.0))
    raise ValueError(f"Regla desconocida: {name}")


def make_prob_model(name: str, seed: int = 0):
    if name == "logit":
        return make_pipeline(StandardScaler(), LogisticRegression(C=1.0, max_iter=500))
    if name == "gbm":
        return HistGradientBoostingClassifier(
            max_iter=200, learning_rate=0.05, max_leaf_nodes=31, min_samples_leaf=200,
            l2_regularization=1.0, early_stopping=False, random_state=seed)
    raise ValueError(f"Modelo desconocido: {name}")


def fit_predict_proba(name: str, X_fit: pd.DataFrame, y_fit: np.ndarray, X_list: list[pd.DataFrame],
                      seed: int = 0, max_rows: int = 400_000):
    """Ajusta con (X_fit, y_fit) y devuelve P(sube) sin calibrar para cada matriz de X_list.

    Si el tramo de ajuste es muy grande se usa una submuestra regular (determinista) para acotar
    el tiempo de cómputo; se registra en los resultados.
    """
    if len(X_fit) > max_rows:
        step = int(np.ceil(len(X_fit) / max_rows))
        X_fit, y_fit = X_fit.iloc[::step], y_fit[::step]
    model = make_prob_model(name, seed)
    model.fit(X_fit[FEATURES].to_numpy(), y_fit)
    return model, [model.predict_proba(X[FEATURES].to_numpy())[:, 1] for X in X_list]


def explain_logit(model, x_row: pd.Series, top: int = 4) -> list[tuple[str, float]]:
    """Contribuciones (coeficiente × valor estandarizado) de las variables más influyentes."""
    scaler = model.named_steps["standardscaler"]
    lr = model.named_steps["logisticregression"]
    z = (x_row[FEATURES].to_numpy(float) - scaler.mean_) / scaler.scale_
    contrib = lr.coef_[0] * z
    order = np.argsort(-np.abs(contrib))[:top]
    return [(FEATURES[i], float(contrib[i])) for i in order]
