"""Estudio 32: lectura de señales de canales y juicio con velas."""

import pandas as pd

from tradingbot.data.telegram_publico import parse_page
from tradingbot.research.study32 import judge, parse_signals


def test_parse_semicolon_list_and_otc_and_timezone():
    pub = pd.Timestamp("2026-10-23T12:40:04+00:00")  # 09:40 en Brasília
    txt = "M1;EURAUD;10:08;PUT\nM1;EURJPY;10:37;CALL\nM1;BTCUSD;10:55;PUT"
    s = parse_signals(txt, pub, -3)
    assert [(x["par"], x["dir"], x["venc_min"]) for x in s] == [("EURAUD", -1, 1), ("EURJPY", 1, 1)]
    assert s[0]["entrada_utc"] == "2026-10-23T13:08:00+00:00"
    assert parse_signals(txt + "\nM1;EURUSD-OTC;10:50;PUT", pub, -3) == []  # mensaje con «OTC»: fuera
    assert parse_signals("M5 EUR/USD 09:00 CALL", pub, -3)[0]["entrada_utc"] == "2026-10-24T12:00:00+00:00"  # ya pasó → mañana
    assert parse_signals("EURUSD 10:00 CALL", pub, -3) == []  # sin vencimiento
    assert parse_signals("M5 EURUSD 10:00 CALL", pub, None) == []  # sin zona horaria


def test_judge_uses_open_of_entry_and_close_of_last_candle():
    t0 = int(pd.Timestamp("2026-10-23 13:08", tz="UTC").timestamp())
    opens = pd.Series({t0: 1.0, t0 + 60: 1.0, t0 + 240: 1.0})
    closes = pd.Series({t0: 1.1, t0 + 60: 0.9, t0 + 240: 0.95})
    sig = {"entrada_utc": "2026-10-23T13:08:00+00:00", "dir": -1, "venc_min": 5}
    assert judge(sig, closes, opens) == "gana"
    assert judge({**sig, "venc_min": 1}, closes, opens) == "pierde"


def test_parse_page_strips_links():
    page = ('<div data-post="canal/7"><div class="tgme_widget_message_text js-message_text" dir="auto">'
            'Hola<br/>https://afiliado.com/x?aff=1</div><time datetime="2026-10-29T10:00:00+00:00"></time></div>')
    p = parse_page(page)[0]
    assert p["id"] == 7 and p["texto"] == "Hola\n[enlace]" and p["publicado_utc"].startswith("2026-10-29")
