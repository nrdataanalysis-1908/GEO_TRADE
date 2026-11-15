import pandas as pd
import pytest

from src.ingestion.market_ingestion import add_features
from test_features import sample_rates


def test_add_features_rejects_duplicate_generated_column_labels():
    rates = sample_rates()
    rates["timestamp_utc"] = pd.to_datetime(rates["time"], unit="s", utc=True)
    rates = pd.concat([rates, rates[["timestamp_utc"]]], axis=1)

    with pytest.raises(ValueError, match="Duplicate feature columns: timestamp_utc"):
        add_features(rates, "EURUSD")


def test_add_features_rejects_duplicate_passthrough_column_labels():
    rates = sample_rates()
    rates = pd.concat([rates, rates[["tick_volume"]]], axis=1)

    with pytest.raises(ValueError, match="Duplicate feature columns: tick_volume"):
        add_features(rates, "EURUSD")
