"""Estudio 3: las variables nuevas son causales y se calculan como dice el pre-registro."""

import numpy as np
import pandas as pd

from tradingbot.research.study3 import NEW_FEATURES, new_features, verdict


def _kl(idx, seed, base=100.0):
    rng = np.random.default_rng(seed)
    c = base * np.exp(np.cumsum(rng.normal(0, 1e-3, len(idx))))
    vol = rng.uniform(1, 2, len(idx))
    return pd.DataFrame({"o": c, "h": c, "l": c, "c": c, "volume": vol, "trades": 10.0,
                         "taker_buy_base": vol * rng.uniform(0, 1, len(idx))}, index=idx)


def test_new_features_are_causal_and_follow_the_registered_definitions():
    idx = pd.date_range("2024-01-01", periods=600, freq="min", tz="UTC")
    spot, perp, prem, other = _kl(idx, 1), _kl(idx, 2), _kl(idx, 3, base=0.001), _kl(idx, 4, base=50.0)
    fund = pd.DataFrame({"fund": [0.0001, 0.0003]},
                        index=pd.DatetimeIndex([idx[0], idx[0] + pd.Timedelta(minutes=300)], name="time"))
    f = new_features(idx, spot, perp, prem, fund, other)
    assert list(f.columns) == NEW_FEATURES and len(NEW_FEATURES) == 19
    t = 400
    # Imbalance de 15 min = 2·Σcompras/Σvolumen − 1 en las velas t−14..t.
    w = spot.iloc[t - 14:t + 1]
    assert np.isclose(f["tib_s_15"].iloc[t], 2 * w["taker_buy_base"].sum() / w["volume"].sum() - 1)
    # Financiación: la de calc_time = minuto 300 vale desde el cierre de la vela 299 (apertura + 1 min).
    assert f["fund"].iloc[298] == 0.0001 and f["fund"].iloc[299] == 0.0003
    # Cambiar todo lo posterior a t no cambia la fila t.
    spot2, perp2, other2 = spot.copy(), perp.copy(), other.copy()
    for df in (spot2, perp2, other2):
        df.iloc[t + 1:] *= 1.5
    f2 = new_features(idx, spot2, perp2, prem, fund, other2)
    pd.testing.assert_series_equal(f.iloc[t], f2.iloc[t])


def test_verdict_applies_all_registered_criteria():
    def res(p, lo, ev, ev_b, imp_lo, pos=0.8, share=0.3, n=1000):
        m = {"n_trades": n, "hit_lo95": lo, "breakeven": 0.5405, "pvalue": p, "ev": ev,
             "positive_fold_frac": pos, "max_fold_profit_share": share}
        return {"modelos": {"precio_mas_bloque_nuevo": m, "referencia_precio": {**m, "ev": ev_b}},
                "logloss": {"mejora_lo95": imp_lo}}

    v = verdict({"BTCUSDT": res(0.001, 0.56, 0.05, 0.01, 0.001), "ETHUSDT": res(0.2, 0.53, 0.0, 0.0, 0.001)})
    assert v["BTCUSDT"]["pasa"] and not v["ETHUSDT"]["pasa"]
    v = verdict({"BTCUSDT": res(0.001, 0.56, 0.05, 0.01, -0.001), "ETHUSDT": res(float("nan"), 0.6, 0.1, 0, 1)})
    assert not v["BTCUSDT"]["pasa"] and not v["BTCUSDT"]["c5_mejora"]  # sin mejora frente al modelo de precio
    assert not v["ETHUSDT"]["c3_holm"]  # p ausente cuenta como 1
