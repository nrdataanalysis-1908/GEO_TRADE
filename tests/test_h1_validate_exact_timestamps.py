import pytest

from src.ingestion.market_ingestion import validate_rates
from test_features import sample_rates


def test_validate_rates_rejects_fractional_timestamp_hidden_by_float_rounding():
    rates = sample_rates()
    rates["time"] = rates["time"].astype(object)
    rates.loc[0, "time"] = "1700000000.0000001"

    clean, rejected = validate_rates(rates)

    assert len(clean) == 39
    assert rejected == 1
