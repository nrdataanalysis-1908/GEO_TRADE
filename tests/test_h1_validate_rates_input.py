import pytest

from src.ingestion.market_ingestion import validate_rates


@pytest.mark.parametrize("rates", [None, [], {}])
def test_validate_rates_requires_a_pandas_dataframe(rates):
    with pytest.raises(TypeError, match="pandas DataFrame"):
        validate_rates(rates)
