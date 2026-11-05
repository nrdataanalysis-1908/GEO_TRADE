import numpy as np
import pandas as pd
import pytest

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


def test_h1_validation_fails_clearly_when_required_market_column_is_missing():
    rates = sample_rates().drop(columns=["spread"])
    with pytest.raises(ValueError, match="Missing required market columns: spread"):
        validate_rates(rates)


@pytest.mark.parametrize(
    ("column", "value"),
    [("high", float("inf")), ("close", float("nan")), ("time", float("inf"))],
)
def test_h1_validation_rejects_non_finite_prices_and_timestamps(column, value):
    rates = sample_rates()
    rates[column] = rates[column].astype(float)
    rates.loc[0, column] = value
    clean, rejected = validate_rates(rates)
    assert len(clean) == 39
    assert rejected == 1


@pytest.mark.parametrize(
    ("column", "value"),
    [("tick_volume", -1), ("spread", float("inf")), ("real_volume", 1.5)],
)
def test_h1_validation_rejects_invalid_volume_and_spread_fields(column, value):
    rates = sample_rates()
    rates[column] = rates[column].astype(float)
    rates.loc[0, column] = value
    clean, rejected = validate_rates(rates)
    assert len(clean) == 39
    assert rejected == 1


@pytest.mark.parametrize("value", ["2026-W45-3", "20261104", "04-11-2026"])
def test_utc_bounds_reject_non_calendar_date_formats(value):
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        utc_bounds(value)


def test_feature_indicators_are_independent_of_input_row_order():
    rates = sample_rates()
    expected = add_features(rates, "EURUSD")
    shuffled = rates.sample(frac=1, random_state=42)
    actual = add_features(shuffled, "EURUSD")
    pd.testing.assert_frame_equal(actual, expected)

def test_h1_validation_rejects_timestamps_outside_pandas_range():
    rates = sample_rates()
    rates.loc[0, "time"] = 10**20
    clean, rejected = validate_rates(rates)
    assert len(clean) == 39
    assert rejected == 1

def test_h1_validation_collapses_identical_duplicate_bars():
    rates = sample_rates()
    rates = pd.concat([rates, rates.iloc[[0]]], ignore_index=True)
    clean, rejected = validate_rates(rates)
    assert len(clean) == 40
    assert rejected == 1
    assert clean["time"].is_unique

def test_utc_day_bounds_are_one_day():
    start, end = utc_bounds("2026-08-21")
    assert str(start) == "2026-08-21 00:00:00+00:00"
    assert (end - start).total_seconds() == 86400
