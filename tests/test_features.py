import numpy as np
import pandas as pd

from src.ingestion.market_ingestion import add_features, validate_rates, utc_bounds


def sample_rates():
    return pd.DataFrame({
        "time": np.arange(1_700_000_000, 1_700_000_000 + 40 * 3600, 3600),
        "open": np.linspace(1.0, 1.04, 40),
        "high": np.linspace(1.01, 1.05, 40),
        "low": np.linspace(0.99, 1.03, 40),
        "close": np.linspace(1.005, 1.045, 40),
        "tick_volume": np.full(40, 100),
        "spread": np.full(40, 2),
        "real_volume": np.zeros(40),
    })


def test_feature_engineering_adds_expected_columns():
    result = add_features(sample_rates(), "EURUSD")
    expected = {"candle_id", "timestamp_utc", "timestamp_brasilia", "range",
                "body", "body_abs", "upper_wick", "lower_wick",
                "candle_direction", "return", "rsi_14", "atr_14",
                "macd", "macd_signal", "bollinger_upper", "volatility_pct"}
    assert expected.issubset(result.columns)
    assert len(result) == 40


def test_ohlc_validation_rejects_invalid_bar():
    rates = sample_rates()
    rates.loc[0, "high"] = 0.5
    clean, rejected = validate_rates(rates)
    assert len(clean) == 39
    assert rejected == 1


def test_utc_day_bounds_are_one_day():
    start, end = utc_bounds("2026-08-21")
    assert str(start) == "2026-08-21 00:00:00+00:00"
    assert (end - start).total_seconds() == 86400
