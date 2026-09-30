"""Decodificación de formatos de proveedores con muestras construidas localmente (sin red)."""

import io
import lzma
import struct
import zipfile
from datetime import date

import numpy as np
import pandas as pd
import pytest

from tradingbot.data import binance, dukascopy, histdata
from tradingbot.data.clean import to_canonical
from tradingbot.instruments import get_instrument


def _bi5(records):
    raw = b"".join(struct.pack(">IIIIIf", *r) for r in records)
    return lzma.compress(raw, format=lzma.FORMAT_ALONE)


def test_dukascopy_url_month_is_zero_based():
    u = dukascopy.day_url("EURUSD", date(2024, 1, 15), "BID")
    assert u.endswith("/EURUSD/2024/00/15/BID_candles_min_1.bi5")


def test_dukascopy_decode_candles():
    inst = get_instrument("EURUSD")
    blob = _bi5([(0, 110000, 110010, 109990, 110020, 1.5), (60, 110010, 110005, 110000, 110015, 2.0)])
    df = dukascopy.decode_candles(blob, date(2024, 1, 15), inst)
    assert df.index[0] == pd.Timestamp("2024-01-15 00:00", tz="UTC")
    assert df.index[1] == pd.Timestamp("2024-01-15 00:01", tz="UTC")
    assert df["o"].iloc[0] == pytest.approx(1.1)
    assert df["c"].iloc[0] == pytest.approx(1.1001)
    assert df["l"].iloc[0] == pytest.approx(1.0999)
    assert df["h"].iloc[0] == pytest.approx(1.1002)
    assert df["v"].iloc[1] == pytest.approx(2.0)


def test_dukascopy_detects_wrong_field_order():
    inst = get_instrument("EURUSD")
    # Si los campos vinieran en otro orden (p. ej., máximo en la posición del mínimo) la validación falla.
    bad = [(i * 60, 110000, 110010, 110050, 109950, 1.0) for i in range(100)]
    with pytest.raises(dukascopy.DecodeError):
        dukascopy.decode_candles(_bi5(bad), date(2024, 1, 15), inst)


def test_dukascopy_detects_wrong_decimal_factor():
    inst = get_instrument("USDJPY")
    blob = _bi5([(0, 150_000_000, 150_000_000, 150_000_000, 150_000_000, 1.0)])  # factor 1e6 por error
    with pytest.raises(dukascopy.DecodeError):
        dukascopy.decode_candles(blob, date(2024, 1, 15), inst)


def test_dukascopy_empty_file():
    df = dukascopy.decode_candles(b"", date(2024, 1, 13), get_instrument("EURUSD"))
    assert df.empty


@pytest.mark.parametrize("scale", [1_000, 1_000_000])
def test_binance_parse_ms_and_us(scale):
    t0 = int(pd.Timestamp("2025-01-01", tz="UTC").timestamp())
    lines = [f"{(t0 + 60 * i) * scale},100000.0,100010.0,99990.0,100005.0,1.5,{(t0 + 60 * i + 59) * scale},0,10,0,0,0"
             for i in range(3)]
    df = binance.parse_klines_csv("\n".join(lines).encode(), get_instrument("BTCUSDT"))
    assert df.index[0] == pd.Timestamp("2025-01-01", tz="UTC")
    assert (df["bid_c"] == df["ask_c"]).all()
    bars, _ = to_canonical(df)
    assert (bars["spread_c"] == 0).all()


def test_histdata_est_to_utc(tmp_path):
    txt = "20240102 170000;1.10000;1.10010;1.09990;1.10005;0\n20240102 170100;1.10005;1.10020;1.10000;1.10010;0\n"
    zpath = tmp_path / "h.zip"
    with zipfile.ZipFile(zpath, "w") as zf:
        zf.writestr("DAT_ASCII_EURUSD_M1_2024.csv", txt)
    df = histdata.load_path(zpath, get_instrument("EURUSD"), assumed_spread=0.0001)
    assert df.index[0] == pd.Timestamp("2024-01-02 22:00", tz="UTC")  # 17:00 EST = 22:00 UTC
    assert np.allclose(df["ask_c"] - df["bid_c"], 0.0001)


def test_clean_marks_closed_market_and_negative_spread():
    idx = pd.date_range("2024-01-05 20:00", periods=180, freq="min", tz="UTC")
    df = pd.DataFrame(index=idx)
    for s, off in (("bid", 0.0), ("ask", 0.0001)):
        for k in ("o", "h", "l", "c"):
            df[f"{s}_{k}"] = 1.1 + off
    df["bid_v"] = 1.0
    df["ask_v"] = 1.0
    df.iloc[60:120, df.columns.get_indexer(["bid_v", "ask_v"])] = 0.0  # 60 min sin ticks → cerrado
    df.iloc[10, df.columns.get_indexer(["bid_v", "ask_v"])] = 0.0  # minuto aislado sin ticks
    df.iloc[5, df.columns.get_loc("ask_c")] = 1.0  # spread negativo
    bars, rep = to_canonical(df)
    assert rep["closed_minutes"] == 60
    assert bars["c"].iloc[60:120].isna().all()
    assert bars["no_tick"].iloc[10] and not np.isnan(bars["c"].iloc[10])
    assert np.isnan(bars["c"].iloc[5]) and rep["negative_spread_minutes"] == 1


def test_histdata_token_extraction():
    from tradingbot.data.histdata_dl import HistDataError, extract_token

    html = '<form><input type="hidden" name="tk" id="tk" value="abc123XYZ" /></form>'
    assert extract_token(html) == "abc123XYZ"
    assert extract_token('<input value="t0k" id="tk">') == "t0k"
    with pytest.raises(HistDataError):
        extract_token("<html>sin token</html>")


def test_histdata_gap_fill_is_causal_and_detects_weekend():
    inst = get_instrument("EURUSD")
    lines = []
    t = pd.Timestamp("2024-01-02 10:00")  # EST
    closes = {0: 1.1000, 1: 1.1002, 4: 1.1005, 5: 1.1001}  # faltan los minutos 2 y 3 (sin ticks)
    for i, c in closes.items():
        ts = (t + pd.Timedelta(minutes=i)).strftime("%Y%m%d %H%M%S")
        lines.append(f"{ts};{c};{c};{c};{c};0")
    # 60 minutos después (hueco largo = mercado cerrado) otro dato
    ts = (t + pd.Timedelta(minutes=70)).strftime("%Y%m%d %H%M%S")
    lines.append(f"{ts};1.2;1.2;1.2;1.2;0")
    raw = histdata.parse_ascii_m1("\n".join(lines), inst, assumed_spread=0.0002)
    bars, rep = to_canonical(raw, fill_gaps=True)
    m2 = pd.Timestamp("2024-01-02 15:02", tz="UTC")
    assert bars.loc[m2, "c"] == pytest.approx(1.1002 + 0.0001)  # plana al cierre ANTERIOR (medio)
    assert bars.loc[m2, "no_tick"]
    assert rep["filled_no_tick_minutes"] == 2
    assert bars.loc[pd.Timestamp("2024-01-02 15:30", tz="UTC"), "c"] != bars.loc[pd.Timestamp("2024-01-02 15:30", tz="UTC"), "c"]  # NaN: cerrado
    # Sin relleno, los minutos faltantes quedan como NaN.
    bars2, _ = to_canonical(raw, fill_gaps=False)
    assert np.isnan(bars2.loc[m2, "c"])


def test_unexpected_gap_detection():
    from tradingbot.data.clean import unexpected_gaps

    idx = pd.date_range("2024-01-01", periods=7 * 1440, freq="min", tz="UTC")  # lunes a domingo
    missing = np.zeros(len(idx), bool)
    missing[1440 * 2 + 600: 1440 * 2 + 900] = True  # miércoles, 5 h sin datos → inesperado
    missing[1440 * 4 + 21 * 60: 1440 * 6 + 22 * 60] = True  # fin de semana → esperado
    g = unexpected_gaps(idx, missing)
    assert g["count"] == 1 and g["largest"][0]["minutes"] == 300
