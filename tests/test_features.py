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

