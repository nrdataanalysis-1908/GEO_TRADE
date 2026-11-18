import pandas as pd

from src.ingestion.market_ingestion import add_features


def _rates():
    return pd.DataFrame({
        "time": [1_700_000_000],
        "open": [1.1],
        "high": [1.3],
        "low": [1.0],
        "close": [1.2],
    })


def test_candle_id_separates_symbol_and_timeframe_boundaries():
    first = add_features(_rates(), "EURUSD_H1", timeframe="M1")
    second = add_features(_rates(), "EURUSD", timeframe="H1_M1")

    assert first["candle_id"].iloc[0] != second["candle_id"].iloc[0]


def test_candle_id_is_deterministic_for_the_same_symbol_timeframe_and_timestamp():
    first = add_features(_rates(), "EURUSD", timeframe="H1")
    second = add_features(_rates(), "EURUSD", timeframe="H1")

    assert first["candle_id"].iloc[0] == second["candle_id"].iloc[0]
