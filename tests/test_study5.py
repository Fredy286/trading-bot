"""Estudio 5: veredicto H5a/H5b con datos sintéticos (nunca con el libro real antes de tiempo)."""

import json

import pandas as pd
import pytest

from tradingbot.live import study5
from tradingbot.live.runner import LIVE_METHOD

POL = {"contract": "binaria", "payout": 0.85, "tie_rule": "refund", "ev_margin": 0.02,
       "allowed_hours_bogota": [0, 24], "feed_latency_s": 1.0, "max_staleness_s": 11.0}
OBS = {"symbol": "BTCUSDT", "model_id": "BTCUSDT-h1-gbm-2026-08-31-e436ef", "policy": POL}


def _rows(start="2026-10-04", end="2026-10-12", hit_every=10, wins_per=6, entry=10.0, **extra):
    """Una alerta por minuto; acierto en `wins_per` de cada `hit_every`; empate 1 de cada 25."""
    out = []
    for i, t in enumerate(pd.date_range(start, end, freq="min", tz="UTC", inclusive="left")):
        tie, win = i % 25 == 24, i % hit_every < wins_per
        out.append({"model_id": OBS["model_id"], "method": LIVE_METHOD, "policy": POL, "time": t.isoformat(),
                    "decision_time": t.isoformat(), "entrada_tras_cierre_s": entry, "tie": tie,
                    "win": win and not tie, "pnl": 0.0 if tie else (0.85 if win else -1.0), **extra})
    return out


def test_pending_shows_counts_but_never_hit_rates():
    v = study5.evaluate(_rows(end="2026-10-06"), OBS, pd.Timestamp("2026-10-06", tz="UTC"))
    assert v["estado"] == "pendiente" and "hipotesis" not in v
    assert v["completa"] == {"H5a": False, "H5b": False}
    text = json.dumps(v)
    assert not any(f'"{k}":' in text for k in ("aciertos", "acierto", "ev", "lo95", "p"))


def test_final_verdict_with_both_samples_complete():
    v = study5.evaluate(_rows(), OBS, pd.Timestamp("2026-10-12", tz="UTC"))
    assert v["estado"] == "final" and v["completa"] == {"H5a": True, "H5b": True}
    a, b = v["hipotesis"]["H5a"], v["hipotesis"]["H5b"]
    assert a["n"] == 3500 and b["n"] == 2500
    assert a["estado"] == "aprueba" and b["estado"] == "aprueba"
    assert a["p_holm"] >= a["p"] and a["umbral"] == pytest.approx(1 / 1.85)
    assert "H5a" in v["conclusion"] or "cualquier hora" in v["conclusion"]
    # H5b solo usa sábados y domingos UTC.
    assert all(pd.Timestamp(d).dayofweek >= 5 for d in b["por_dia_utc"])


def test_no_edge_does_not_pass():
    v = study5.evaluate(_rows(wins_per=5), OBS, pd.Timestamp("2026-10-12", tz="UTC"))
    assert {h["estado"] for h in v["hipotesis"].values()} == {"no aprueba"}
    assert "SIN SEÑAL" in v["conclusion"]


def test_incomplete_sample_after_deadline_is_inconclusive():
    """Al vencer el plazo con una muestra incompleta: «no concluyente» y entra en Holm con p = 1."""
    rows = [r for r in _rows() if pd.Timestamp(r["decision_time"]).dayofweek < 5 or
            pd.Timestamp(r["decision_time"]) < pd.Timestamp("2026-10-04 12:00", tz="UTC")]
    v = study5.evaluate(rows, OBS, pd.Timestamp("2026-12-14", tz="UTC"))
    assert v["estado"] == "final" and v["hipotesis"]["H5b"]["estado"] == "no concluyente"
    assert v["hipotesis"]["H5a"]["p_holm"] == pytest.approx(min(1.0, 2 * v["hipotesis"]["H5a"]["p"]))


def test_only_registered_model_policy_period_and_one_row_per_candle():
    rows = _rows()
    extra = [{**rows[0], "policy": {**POL, "payout": 0.92}}, {**rows[0], "model_id": "otro"},
             {**rows[0], "decision_time": "2026-10-03T23:59:00+00:00", "time": "2026-10-03T23:59:00+00:00"},
             {**rows[1]}]
    elig, excl = study5.eligible_rows(rows + extra, OBS)
    assert len(elig) == len(rows)
    assert excl == {"de_otro_modelo_o_metodo": 1, "politica_distinta": 1, "fuera_del_periodo": 1,
                    "vela_de_decision_repetida": 1}


def test_ledger_with_another_entry_delay_is_rejected():
    with pytest.raises(ValueError, match="10"):
        study5.evaluate(_rows(entry=2.0), OBS, pd.Timestamp("2026-10-12", tz="UTC"))


def test_weekend_is_decided_in_utc():
    assert study5.is_weekend({"decision_time": "2026-10-04T23:59:00+00:00"})  # domingo UTC
    assert not study5.is_weekend({"decision_time": "2026-10-05T00:30:00+00:00"})  # domingo en Bogotá, lunes UTC


def test_cli_writes_verdict(tmp_path):
    from tradingbot.cli import main

    reg = tmp_path / "obs.json"
    reg.write_text(json.dumps({**OBS, "horizon": 1, "model": "gbm", "sample_n": 3500, "max_days": 56}),
                   encoding="utf-8")
    run = tmp_path / "rt"
    run.mkdir()
    (run / "paper_ledger.jsonl").write_text("".join(json.dumps(r) + "\n" for r in _rows(end="2026-10-05")),
                                            encoding="utf-8")
    out = tmp_path / "v.json"
    assert main(["study5-verdict", "--runtime", str(run), "--end", "2026-10-05", "--observation", str(reg),
                 "--out", str(out)]) == 0
    assert json.loads(out.read_text(encoding="utf-8"))["estado"] == "pendiente"
