import numpy as np

from src.ingestion.market_ingestion import validate_rates
from test_features import sample_rates


def test_h1_counters_preserve_int64_precision_and_reject_overflow():
    rates = sample_rates()
    rates["tick_volume"] = rates["tick_volume"].astype(object)
    rates.loc[0, "tick_volume"] = 2**53 + 1
    rates.loc[1, "tick_volume"] = 2**63

    clean, rejected = validate_rates(rates)

    preserved = clean.loc[clean["time"] == 1_700_000_000, "tick_volume"].iloc[0]
    assert preserved == 2**53 + 1
    assert isinstance(preserved, (int, np.integer))
    assert clean["tick_volume"].dtype == np.dtype("int64")
    assert len(clean) == 39
    assert rejected == 1
