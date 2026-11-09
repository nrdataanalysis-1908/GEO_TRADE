import pandas as pd

from src.ingestion.market_ingestion import validate_rates
from test_features import sample_rates


def test_h1_rejects_duplicate_timestamp_when_only_volume_fields_conflict():
    rates = sample_rates()
    conflicting = rates.iloc[[0]].copy()
    conflicting.loc[:, "tick_volume"] = conflicting["tick_volume"] + 1
    combined = pd.concat([rates, conflicting], ignore_index=True)

    clean, rejected = validate_rates(combined)

    assert len(clean) == 39
    assert rejected == 2
    assert clean["time"].is_unique
