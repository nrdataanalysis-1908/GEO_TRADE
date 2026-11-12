import pytest

from src.ingestion.market_ingestion import add_features
from test_features import sample_rates


def test_add_features_rejects_fractional_timestamp_hidden_by_float_rounding():
    rates = sample_rates()
    rates["time"] = rates["time"].astype(object)
    rates.loc[0, "time"] = "1700000000.0000001"

    with pytest.raises(ValueError, match="exact integral Unix seconds"):
        add_features(rates, "EURUSD")


def test_add_features_accepts_exact_integral_decimal_timestamp_text():
    rates = sample_rates()
    rates["time"] = rates["time"].astype(object)
    rates.loc[0, "time"] = "1700000000.0"

    result = add_features(rates, "EURUSD")

    assert result.loc[0, "time"] == 1_700_000_000
