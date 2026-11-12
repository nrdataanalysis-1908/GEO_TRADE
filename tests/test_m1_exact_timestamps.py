from src.ingestion.trade2_geo_trade_v2 import validar_candle


def _candle(timestamp):
    return {
        "time": timestamp,
        "open": 1.1, "high": 1.3, "low": 1.0, "close": 1.2,
        "tick_volume": 10, "spread": 2, "real_volume": 0,
    }


def test_m1_rejects_fractional_timestamp_hidden_by_float_rounding():
    assert validar_candle(_candle("1700000000.0000001")) is False


def test_m1_accepts_exact_integral_decimal_timestamp_text():
    assert validar_candle(_candle("1700000000.0")) is True
