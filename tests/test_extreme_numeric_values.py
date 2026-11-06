import pytest

from src.ingestion.market_ingestion import validate_rates

from test_features import sample_rates


@pytest.mark.parametrize("column", ["time", "open", "high", "low", "close", "tick_volume", "spread", "real_volume"])
def test_h1_validation_rejects_integers_too_large_for_float_conversion(column):
    rates = sample_rates()
    rates[column] = rates[column].astype(object)
    rates.loc[0, column] = 10**400

    clean, rejected = validate_rates(rates)

    assert len(clean) == 39
    assert rejected == 1
