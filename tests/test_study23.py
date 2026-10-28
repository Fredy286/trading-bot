"""Estudio 23: lectura de horas de entrada de los canales."""

import pandas as pd

from tradingbot.research.study23 import entry_utc, tz_offset


def test_timezone_parsing():
    assert tz_offset("UTC -3") == -3 and tz_offset("UTC+05:30 en sus listas") == 5.5
    assert tz_offset("no declarada (canal brasileño; probable UTC−3 Brasília)") == -3
    assert tz_offset("sin datos") is None


def test_entry_time_rules():
    pub = pd.Timestamp("2025-07-21 01:57", tz="UTC")  # 22:57 del 20/07 en Brasília
    assert entry_utc("21/07/2025 00:30", pub, -3) == pd.Timestamp("2025-07-21 03:30", tz="UTC")
    assert entry_utc("21/07 00:30", pub, -3) == pd.Timestamp("2025-07-21 03:30", tz="UTC")
    # Solo la hora: la primera vez que llega DESPUÉS de la publicación
    assert entry_utc("22:50", pub, -3) == pd.Timestamp("2025-07-22 01:50", tz="UTC")
    assert entry_utc("23:10:00", pub, -3) == pd.Timestamp("2025-07-21 02:10", tz="UTC")
