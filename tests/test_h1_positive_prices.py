import pytest

from src.ingestion.market_ingestion import validate_rates
from test_features import sample_rates


@pytest.mark.parametrize("value", [0.0, -0.01])
def test_h1_validation_rejects_non_positive_ohlc_prices(value):
    rates = sample_rates()
    rates.loc[0, ["open", "high", "low", "close"]] = value

    clean, rejected = validate_rates(rates)

    assert len(clean) == 39
    assert rejected == 1
