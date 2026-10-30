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


def test_audit_day_requests_candles_in_blocks_of_at_most_1000(tmp_path):
    import json

    from tradingbot.research.study32 import audit_day

    calls = []

    class Feed:
        def _call(self, req):
            calls.append(req)
            n = (req["end"] - req["start"]) // 60 + 1
            assert n <= 1000
            ep = range(req["start"], req["end"] + 1, 60)
            return {"candles": [{"epoch": e, "open": 1.0, "close": 1.0 - 1e-4} for e in ep]}

    (tmp_path / "lista.txt").write_text("canalx -3\n", encoding="utf-8")
    (tmp_path / "can" / "canalx").mkdir(parents=True)
    msg = {"id": 1, "publicado_utc": "2026-11-02T12:00:00+00:00", "texto": "M1;EURUSD;20:30;PUT"}
    (tmp_path / "can" / "canalx" / "2026-11-02.jsonl").write_text(json.dumps(msg) + "\n", encoding="utf-8")
    out = audit_day("2026-11-02", feed=Feed(), root=tmp_path / "can", out=tmp_path / "out",
                    lista=tmp_path / "lista.txt", log=lambda *_: None)
    assert out == {"canalx": 1} and len(calls) >= 2  # 20:30 Brasília = 23:30 UTC: necesita el segundo bloque
    row = json.loads((tmp_path / "out" / "canalx" / "2026-11-02.jsonl").read_text(encoding="utf-8"))
    assert row["resultado"] == "gana"


def test_dated_list_keeps_its_date_and_drops_hours_already_past():
    pub = pd.Timestamp("2026-10-30T03:42:37+00:00")  # 00:42 del 30/10 en Brasília
    txt = "Lista m1 30/10\n\nM1;GBPJPY;00:08;PUT\nM1;EURAUD;00:42;PUT\nM1;AUDUSD;02:12;CALL"
    s = parse_signals(txt, pub, -3)
    assert [x["entrada_utc"] for x in s] == ["2026-10-30T05:12:00+00:00"]  # 00:08 y 00:42 ya pasaron: fuera
    pub2 = pd.Timestamp("2026-10-22T01:22:02+00:00")  # 22:22 del 21/10 en Brasília, lista del día siguiente
    s2 = parse_signals("🗓 22/10/2026\n⏳M5 EURUSD 00:25 PUT 🟥", pub2, -3)
    assert s2[0]["entrada_utc"] == "2026-10-22T03:25:00+00:00"
    pub3 = pd.Timestamp("2027-01-01T02:00:00+00:00")  # 23:00 del 31/12 en Brasília: «01/01» es del año siguiente
    assert parse_signals("Sinais 01/01\nM5;EURUSD;09:00;CALL", pub3, -3)[0]["entrada_utc"] == "2027-01-01T12:00:00+00:00"
    assert parse_signals("Sinais 31/12\nM5;EURUSD;09:00;CALL", pub3, -3) == []  # 31/12 09:00 ya pasó


def test_capture_keeps_long_lists():
    from tradingbot.data.telegram_publico import MAX_TEXT

    assert MAX_TEXT >= 4096
