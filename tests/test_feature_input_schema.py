import numpy as np
import pandas as pd
import pytest

from src.ingestion.market_ingestion import add_features


def _rates():
    return pd.DataFrame({
        "time": np.arange(1_700_000_000, 1_700_000_000 + 20 * 3600, 3600),
        "open": np.linspace(1.0, 1.02, 20),
        "high": np.linspace(1.01, 1.03, 20),
        "low": np.linspace(0.99, 1.01, 20),
        "close": np.linspace(1.005, 1.025, 20),
    })


def test_feature_engineering_reports_missing_required_columns():
    with pytest.raises(ValueError, match="Missing required feature columns: open"):
        add_features(_rates().drop(columns=["open"]), "EURUSD")


def test_feature_engineering_rejects_duplicate_required_columns():
    rates = _rates()
    rates = pd.concat([rates, rates[["close"]]], axis=1)
    with pytest.raises(ValueError, match="Duplicate feature columns: close"):
        add_features(rates, "EURUSD")


def test_feature_engineering_rejects_empty_symbol_and_timeframe():
    with pytest.raises(ValueError, match="symbol"):
        add_features(_rates(), " ")
    with pytest.raises(ValueError, match="timeframe"):
        add_features(_rates(), "EURUSD", timeframe="")


def test_feature_engineering_rejects_empty_rate_frames():
    with pytest.raises(ValueError, match="at least one"):
        add_features(_rates().iloc[0:0], "EURUSD")
