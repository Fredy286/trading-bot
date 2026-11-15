"""Horario del blitz con precio real en IQ Option (enmienda 2026-11-15 a los Estudios 44, 46 y 68)."""

import json

import pandas as pd

from tradingbot.live import horario_iq as hi


def _t(s):
    return pd.Timestamp(s, tz="UTC")


def test_prudent_schedule_edges():
    # Domingo 21:59 de Bogotá = lunes 02:59 UTC. La vela t compra a t + 1 min y vence a t + 4 min.
    assert not hi.abierto(_t("2026-11-16 02:58"))   # compra 02:59 UTC (domingo 21:59 Bogotá): cerrado
    assert hi.abierto(_t("2026-11-16 02:59"))       # compra 03:00 UTC (domingo 22:00 Bogotá): abierto
    assert hi.abierto(_t("2026-11-18 12:00"))       # miércoles
    assert hi.abierto(_t("2026-11-20 21:56"))       # viernes: vence justo a las 22:00 UTC
    assert not hi.abierto(_t("2026-11-20 21:57"))   # su vencimiento pasa el cierre del viernes
    assert not hi.abierto(_t("2026-11-21 12:00"))   # sábado
    assert not hi.abierto(_t("2026-11-22 23:00"))   # domingo
    v = pd.date_range("2026-11-16", "2026-11-23", freq="min", tz="UTC", inclusive="left")
    ab = hi.abierto_vec(v)
    # velas abiertas: de lunes 02:59 (compra 03:00) a viernes 21:56 (vence 22:00), ambas incluidas
    assert ab.sum() == (4 * 1440 + 21 * 60 + 56) - (2 * 60 + 59) + 1


def test_pauses_and_config(tmp_path):
    h = {**hi.PRUDENTE, "pausas": [{"desde": "12:00", "hasta": "12:30"}]}
    assert not hi.abierto(_t("2026-11-18 11:57"), h)  # el contrato 11:58–12:01 cruza la pausa
    assert hi.abierto(_t("2026-11-18 11:55"), h)      # 11:56–11:59
    assert hi.abierto(_t("2026-11-18 12:29"), h)      # compra 12:30
    f = tmp_path / "h.json"
    f.write_text(json.dumps({**hi.PRUDENTE, "confirmado_por_usuario": True}))
    assert hi.cargar(f)["confirmado_por_usuario"] and hi.cargar(tmp_path / "no.json") == hi.PRUDENTE
    assert hi.cargar()["zona"] == "UTC"  # el del repo
