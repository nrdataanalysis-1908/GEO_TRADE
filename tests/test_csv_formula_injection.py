import pytest

from test_features import sample_rates
from src.ingestion.market_ingestion import add_features, validate_symbols


@pytest.mark.parametrize("prefix", ["=", "+", "-", "@"])
def test_h1_symbol_arguments_reject_spreadsheet_formula_prefixes(prefix):
    with pytest.raises(ValueError, match="spreadsheet formula"):
        validate_symbols([f"{prefix}SUM"])


@pytest.mark.parametrize("prefix", ["=", "+", "-", "@"])
def test_add_features_rejects_formula_like_symbols(prefix):
    with pytest.raises(ValueError, match="spreadsheet formula"):
        add_features(sample_rates(), f"{prefix}SYMBOL")


@pytest.mark.parametrize("prefix", ["=", "+", "-", "@"])
def test_add_features_rejects_formula_like_timeframes(prefix):
    with pytest.raises(ValueError, match="spreadsheet formula"):
        add_features(sample_rates(), "EURUSD", timeframe=f"{prefix}H1")