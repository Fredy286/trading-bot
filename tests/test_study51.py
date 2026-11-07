import numpy as np
import pandas as pd

from tradingbot.research import study51


def test_closes_uses_gate_only_from_2025_09(monkeypatch):
    calls = []

    def fake(symbol, venue, ym):
        calls.append((symbol, venue, ym))
        idx = pd.date_range(ym + "-01", periods=3, freq="min", tz="UTC")
        return pd.Series(np.arange(3, dtype=float), index=idx)

    monkeypatch.setattr(study51.bolsas, "month_closes", fake)
    cl = study51.closes("2025-07", "2025-10", "2025-09")
    assert {s for s, _, _ in calls} == {"ETHUSDT"}
    assert [m for _, v, m in calls if v == "gate"] == ["2025-09", "2025-10"]
    assert [m for _, v, m in calls if v == "okx"] == ["2025-07", "2025-08", "2025-09", "2025-10"]
    assert all(x.index.is_monotonic_increasing and x.index.is_unique for x in cl.values())


def test_btc_signals_follow_the_policy(tmp_path, monkeypatch):
    idx = pd.date_range("2025-09-01", periods=4, freq="min", tz="UTC")
    pred = pd.DataFrame({"p": [0.70, 0.52, 0.42, 0.565], "q": 0.0}, index=idx)
    f = tmp_path / "pred.parquet"
    pred.to_parquet(f)
    monkeypatch.setattr(study51, "PRED", f)
    assert list(study51.btc_signals(0.02, None)) == [idx[0], idx[2], idx[3]]  # EV ≥ 0,02 ⇔ p ≥ 0,5484
    assert list(study51.btc_signals(0.02, 0.57)) == [idx[0], idx[2]]
