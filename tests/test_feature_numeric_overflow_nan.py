import numpy as np
import pytest

from src.ingestion.market_ingestion import add_features
from test_features import sample_rates


def test_feature_engineering_rejects_rolling_overflow_that_becomes_nan():
    rates = sample_rates()
    prices = np.where(
        np.arange(len(rates)) % 2 == 0,
        1.6e308,
        1.7e308,
    )
    rates["open"] = prices
    rates["close"] = prices
    rates["high"] = 1.75e308
    rates["low"] = 1.5e308

    with pytest.raises(ValueError, match="non-finite"):
        add_features(rates, "EURUSD")
