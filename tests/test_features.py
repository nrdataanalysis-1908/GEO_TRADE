import numpy as np
from pathlib import Path
import pandas as pd
import pytest

from src.ingestion import market_ingestion
from src.ingestion.market_ingestion import (
    add_features, validate_rates, utc_bounds, validate_symbols, _write_csv_atomically,
)


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


@pytest.mark.parametrize(
    "symbols",
    [
        [],
        [""],
        [" EURUSD"],
        ["EURUSD", "EURUSD"],
        ["EUR\nUSD"],
    ],
)
def test_h1_symbol_validation_rejects_ambiguous_arguments(symbols):
    with pytest.raises(ValueError):
        validate_symbols(symbols)


def test_h1_symbol_validation_preserves_order_and_none_means_all_symbols():
    assert validate_symbols(["EURUSD", "GBPUSD"]) == ["EURUSD", "GBPUSD"]
    assert validate_symbols(None) is None


@pytest.mark.parametrize(
    ("column", "value"),
    [
        ("time", float("nan")),
        ("time", 1.5),
        ("open", float("inf")),
        ("high", 0.5),
    ],
)
def test_add_features_rejects_invalid_timestamp_and_ohlc_values(column, value):
    rates = sample_rates()
    rates[column] = rates[column].astype(float)
    rates.loc[0, column] = value
    with pytest.raises(ValueError):
        add_features(rates, "EURUSD")


def test_add_features_rejects_duplicate_timestamps():
    rates = sample_rates()
    rates.loc[1, "time"] = rates.loc[0, "time"]
    with pytest.raises(ValueError):
        add_features(rates, "EURUSD")


def test_h1_main_reports_output_directory_creation_failure(monkeypatch, capsys):
    from types import SimpleNamespace

    class BlockedDirectory:
        def mkdir(self, *args, **kwargs):
            raise PermissionError("permission denied")

    args = SimpleNamespace(
        date="2026-11-03",
        symbols=None,
        output_dir=BlockedDirectory(),
        terminal_path=None,
    )
    monkeypatch.setattr(market_ingestion, "parse_args", lambda: args)
    monkeypatch.setattr(market_ingestion, "mt5", object())

    assert market_ingestion.main() == 1
    assert "output directory" in capsys.readouterr().out.lower()


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


def test_utc_bounds_rejects_date_without_exclusive_next_day():
    with pytest.raises(ValueError, match="exclusive next-day"):
        utc_bounds("9999-12-31")


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
    rates["time"] = rates["time"].astype(object)
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

def test_h1_validation_rejects_conflicting_duplicate_bars():
    rates = sample_rates()
    conflicting = rates.iloc[[0]].copy()
    conflicting.loc[:, "close"] = 1.006
    rates = pd.concat([rates, conflicting], ignore_index=True)
    clean, rejected = validate_rates(rates)
    assert len(clean) == 39
    assert rejected == 2
    assert clean["time"].is_unique

@pytest.mark.parametrize(
    ("column", "value"),
    [("time", True), ("open", True), ("high", True), ("low", True),
     ("close", True), ("tick_volume", True), ("spread", True), ("real_volume", True)],
)
def test_h1_validation_rejects_boolean_market_values(column, value):
    rates = sample_rates()
    rates[column] = rates[column].astype(object)
    rates.loc[0, column] = value
    clean, rejected = validate_rates(rates)
    assert len(clean) == 39
    assert rejected == 1

def test_h1_validation_rejects_duplicate_market_columns():
    rates = sample_rates()
    rates = pd.concat([rates, rates[["close"]]], axis=1)
    with pytest.raises(ValueError, match="Duplicate market columns: close"):
        validate_rates(rates)

def test_main_returns_usage_error_for_invalid_calendar_date(monkeypatch, capsys):
    from argparse import Namespace
    from unittest.mock import patch
    import src.ingestion.market_ingestion as market

    monkeypatch.setattr(market, "mt5", object())
    monkeypatch.setattr(market, "parse_args", lambda: Namespace(date="2026-02-30"))
    assert market.main() == 2
    assert "Invalid date" in capsys.readouterr().out

def test_h1_validation_returns_bars_in_chronological_order():
    rates = sample_rates().iloc[::-1].reset_index(drop=True)
    clean, rejected = validate_rates(rates)
    assert rejected == 0
    assert clean["time"].is_monotonic_increasing


def test_utc_day_bounds_are_one_day():
    start, end = utc_bounds("2026-08-21")
    assert str(start) == "2026-08-21 00:00:00+00:00"
    assert (end - start).total_seconds() == 86400


def test_h1_main_returns_failure_when_any_symbol_fails_after_export(monkeypatch, tmp_path, capsys):
    from argparse import Namespace
    from types import SimpleNamespace
    import src.ingestion.market_ingestion as market

    featured = add_features(sample_rates(), "GOOD")
    fake_mt5 = SimpleNamespace(
        initialize=lambda **kwargs: True,
        account_info=lambda: SimpleNamespace(login=123, server="test-server"),
        shutdown=lambda: None,
    )
    monkeypatch.setattr(market, "mt5", fake_mt5)
    monkeypatch.setattr(
        market,
        "parse_args",
        lambda: Namespace(
            date="2026-08-21",
            symbols=["GOOD", "BAD"],
            terminal_path="unused",
            output_dir=tmp_path,
        ),
    )

    def collect(symbol, start, end):
        if symbol == "GOOD":
            return featured, 0, None
        return None, 0, "simulated symbol failure"

    monkeypatch.setattr(market, "collect_symbol", collect)

    assert market.main() == 1
    assert list(tmp_path.glob("GEO_TRADE_MARKET_H1_DAY_20260821_*.csv"))
    assert "errors=1" in capsys.readouterr().out


def test_h1_atomic_csv_export_preserves_previous_file_on_write_failure(monkeypatch, tmp_path):
    destination = tmp_path / "market.csv"
    destination.write_text("previous-complete-export", encoding="utf-8")

    def fail_after_partial_write(self, path, **kwargs):
        Path(path).write_text("partial", encoding="utf-8")
        raise OSError("simulated disk write failure")

    monkeypatch.setattr(pd.DataFrame, "to_csv", fail_after_partial_write)
    with pytest.raises(OSError, match="simulated disk write failure"):
        _write_csv_atomically(sample_rates(), destination, ["time"])

    assert destination.read_text(encoding="utf-8") == "previous-complete-export"
    assert not list(tmp_path.glob(".market.csv.*.tmp"))

def test_feature_engineering_rejects_overflowed_derived_metrics():
    rates = sample_rates().iloc[:2].copy()
    rates.loc[0, ["open", "high", "low", "close"]] = [
        1e-308, 2e-308, 5e-309, 1.5e-308,
    ]
    rates.loc[1, ["open", "high", "low", "close"]] = [
        1e308, 1.5e308, 0.9e308, 1.2e308,
    ]

    with pytest.raises(ValueError, match="non-finite"):
        add_features(rates, "EURUSD")

def test_rsi_assigns_neutral_value_to_a_flat_market_window():
    rates = sample_rates()
    rates["open"] = 1.0
    rates["high"] = 1.01
    rates["low"] = 0.99
    rates["close"] = 1.0

    result = add_features(rates, "EURUSD")

    assert result["rsi_14"].iloc[:13].isna().all()
    assert (result["rsi_14"].iloc[13:] == 50).all()


def test_add_features_rejects_complex_market_prices():
    rates = sample_rates().iloc[:2].copy()
    rates["close"] = rates["close"].astype(object)
    rates.loc[0, "close"] = 1.005 + 0.25j

    with pytest.raises(ValueError, match="real"):
        add_features(rates, "EURUSD")


def test_h1_validation_rejects_complex_price_rows_without_real_part_coercion():
    rates = sample_rates()
    rates["close"] = rates["close"].astype(object)
    rates.loc[0, "close"] = 1.005 + 0.25j

    clean, rejected = validate_rates(rates)

    assert len(clean) == 39
    assert rejected == 1
    assert np.isrealobj(clean["close"].to_numpy())


@pytest.mark.parametrize("column", ["time", "open", "high", "low", "close"])
def test_add_features_rejects_boolean_market_inputs(column):
    rates = sample_rates()
    rates[column] = rates[column].astype(object)
    rates.loc[0, column] = True

    with pytest.raises(ValueError):
        add_features(rates, "EURUSD")


def test_h1_validation_drops_unrepresentable_integer_price_without_losing_valid_rows():
    rates = sample_rates()
    rates["open"] = rates["open"].astype(object)
    rates.loc[0, "open"] = 10**400

    clean, rejected = validate_rates(rates)

    assert len(clean) == len(rates) - 1
    assert rejected == 1
    assert clean["time"].is_monotonic_increasing


def test_add_features_does_not_mutate_input_dataframe():
    rates = sample_rates()
    original = rates.copy(deep=True)

    result = add_features(rates, "EURUSD")

    pd.testing.assert_frame_equal(rates, original)
    assert "timestamp_utc" in result.columns
    assert "timestamp_utc" not in rates.columns


def test_feature_warmup_preserves_only_documented_rolling_null_windows():
    result = add_features(sample_rates(), "EURUSD")

    assert result["sma_5"].iloc[:4].isna().all()
    assert result["sma_5"].iloc[4:].notna().all()
    assert result["sma_10"].iloc[:9].isna().all()
    assert result["sma_10"].iloc[9:].notna().all()
    assert result["rsi_14"].iloc[:13].isna().all()
    assert result["rsi_14"].iloc[13:].notna().all()
    assert result["atr_14"].iloc[:13].isna().all()
    assert result["atr_14"].iloc[13:].notna().all()
    assert result["bollinger_middle"].iloc[:19].isna().all()
    assert result["bollinger_middle"].iloc[19:].notna().all()
    numeric = result.select_dtypes(include=[np.number]).to_numpy(dtype=float)
    assert not np.isinf(numeric).any()


def test_h1_validation_does_not_mutate_input_dataframe():
    rates = sample_rates()
    original = rates.copy(deep=True)

    clean, rejected = validate_rates(rates)

    pd.testing.assert_frame_equal(rates, original)
    assert len(clean) == len(rates)
    assert rejected == 0


def test_h1_validation_does_not_mutate_source_when_rejecting_rows():
    rates = sample_rates()
    rates.loc[0, "close"] = np.nan
    original = rates.copy(deep=True)

    clean, rejected = validate_rates(rates)

    pd.testing.assert_frame_equal(rates, original)
    assert len(clean) == len(rates) - 1
    assert rejected == 1

def test_rsi_reaches_expected_boundaries_for_one_directional_market():
    for close, expected in (
        (np.linspace(1.0, 1.04, 40), 100.0),
        (np.linspace(1.04, 1.0, 40), 0.0),
    ):
        rates = sample_rates()
        rates["close"] = close
        rates["open"] = close
        rates["high"] = close + 0.001
        rates["low"] = close - 0.001

        result = add_features(rates, "EURUSD")
        assert (result["rsi_14"].iloc[13:] == expected).all()

def test_atr_uses_previous_close_for_true_range_gaps():
    rates = sample_rates().iloc[:15].copy()
    previous_close = rates.loc[13, "close"]
    rates.loc[14, "low"] = previous_close + 0.02
    rates.loc[14, "open"] = previous_close + 0.03
    rates.loc[14, "close"] = previous_close + 0.025
    rates.loc[14, "high"] = previous_close + 0.04

    result = add_features(rates, "EURUSD")
    prior_close = result["close"].shift()
    true_range = pd.concat(
        [
            result["high"] - result["low"],
            (result["high"] - prior_close).abs(),
            (result["low"] - prior_close).abs(),
        ],
        axis=1,
    ).max(axis=1)

    assert true_range.iloc[14] == pytest.approx(0.04)
    assert result["atr_14"].iloc[14] == pytest.approx(
        true_range.rolling(14).mean().iloc[14]
    )

def test_bollinger_bands_use_sample_standard_deviation():
    rates = sample_rates()
    result = add_features(rates, "EURUSD")
    window = rates["close"].iloc[-20:]
    expected_middle = window.mean()
    expected_std = window.std(ddof=1)

    assert result["bollinger_middle"].iloc[-1] == pytest.approx(expected_middle)
    assert result["bollinger_upper"].iloc[-1] == pytest.approx(
        expected_middle + 2 * expected_std
    )
    assert result["bollinger_lower"].iloc[-1] == pytest.approx(
        expected_middle - 2 * expected_std
    )

def test_volatility_uses_sample_standard_deviation_of_simple_returns():
    rates = sample_rates()
    result = add_features(rates, "EURUSD")
    expected = rates["close"].pct_change().rolling(10).std(ddof=1).iloc[-1]

    assert result["volatility_10"].iloc[-1] == pytest.approx(expected)
    assert result["volatility_pct"].iloc[-1] == pytest.approx(expected * 100)

def test_ema_uses_recursive_adjust_false_convention():
    rates = sample_rates()
    result = add_features(rates, "EURUSD")
    expected = rates["close"].ewm(span=5, adjust=False).mean()

    pd.testing.assert_series_equal(
        result["ema_5"].reset_index(drop=True),
        expected.reset_index(drop=True),
        check_names=False,
    )

def test_macd_signal_and_histogram_follow_documented_ema_periods():
    rates = sample_rates()
    result = add_features(rates, "EURUSD")
    ema_12 = rates["close"].ewm(span=12, adjust=False).mean()
    ema_26 = rates["close"].ewm(span=26, adjust=False).mean()
    expected_macd = ema_12 - ema_26
    expected_signal = expected_macd.ewm(span=9, adjust=False).mean()

    assert result["macd"].iloc[-1] == pytest.approx(expected_macd.iloc[-1])
    assert result["macd_signal"].iloc[-1] == pytest.approx(expected_signal.iloc[-1])
    assert result["macd_histogram"].iloc[-1] == pytest.approx(
        expected_macd.iloc[-1] - expected_signal.iloc[-1]
    )

def test_rsi_uses_simple_rolling_gain_and_loss_averages():
    rates = sample_rates()
    result = add_features(rates, "EURUSD")
    delta = rates["close"].diff()
    average_gain = delta.clip(lower=0).rolling(14).mean()
    average_loss = -delta.clip(upper=0).rolling(14).mean()
    relative_strength = average_gain / average_loss.replace(0, np.nan)
    expected = 100 - 100 / (1 + relative_strength)
    expected.loc[(average_loss == 0) & (average_gain > 0)] = 100
    expected.loc[(average_loss == 0) & (average_gain == 0)] = 50

    pd.testing.assert_series_equal(
        result["rsi_14"].reset_index(drop=True),
        expected.reset_index(drop=True),
        check_names=False,
    )

def test_h1_brasilia_timestamps_respect_historical_dst_offsets():
    rates = sample_rates().iloc[:2].copy()
    rates["time"] = [
        int(pd.Timestamp("2018-11-04T03:00:00Z").timestamp()),
        int(pd.Timestamp("2019-02-17T02:00:00Z").timestamp()),
    ]

    result = add_features(rates, "EURUSD")

    assert str(result["timestamp_brasilia"].iloc[0]) == "2018-11-04 01:00:00-02:00"
    assert str(result["timestamp_brasilia"].iloc[1]) == "2019-02-16 23:00:00-03:00"

def test_candle_direction_distinguishes_buy_sell_and_doji():
    rates = sample_rates().iloc[:3].copy()
    rates["open"] = [1.0, 1.1, 1.1]
    rates["close"] = [1.1, 1.0, 1.1]
    rates["high"] = [1.2, 1.2, 1.2]
    rates["low"] = [0.9, 0.9, 0.9]

    result = add_features(rates, "EURUSD")

    assert result["candle_direction"].tolist() == ["BUY", "SELL", "DOJI"]

def test_candle_anatomy_matches_ohlc_geometry():
    rates = sample_rates().iloc[:3].copy()
    rates["open"] = [1.0, 1.1, 1.1]
    rates["close"] = [1.1, 1.0, 1.1]
    rates["high"] = [1.2, 1.2, 1.2]
    rates["low"] = [0.9, 0.9, 0.9]

    result = add_features(rates, "EURUSD")

    assert result["range"].tolist() == pytest.approx([0.3, 0.3, 0.3])
    assert result["body"].tolist() == pytest.approx([0.1, -0.1, 0.0])
    assert result["body_abs"].tolist() == pytest.approx([0.1, 0.1, 0.0])
    assert result["upper_wick"].tolist() == pytest.approx([0.1, 0.1, 0.1])
    assert result["lower_wick"].tolist() == pytest.approx([0.1, 0.1, 0.2])

def test_add_features_reports_missing_required_columns():
    rates = sample_rates().drop(columns=["high"])

    with pytest.raises(ValueError, match="Missing required feature columns: high"):
        add_features(rates, "EURUSD")

def test_add_features_rejects_duplicate_required_columns():
    rates = sample_rates()
    rates = pd.concat([rates, rates[["close"]]], axis=1)

    with pytest.raises(ValueError, match="Duplicate feature columns: close"):
        add_features(rates, "EURUSD")

@pytest.mark.parametrize("timeframe", ["", " H1", "H1 ", "H1\\n"])
def test_add_features_rejects_ambiguous_timeframe_labels(timeframe):
    with pytest.raises(ValueError, match="timeframe must be a non-empty trimmed string"):
        add_features(sample_rates(), "EURUSD", timeframe=timeframe)

