import pandas as pd
import pytest

from src.ingestion.market_ingestion import validate_rates


def test_validate_rates_reports_mixed_type_duplicate_labels_as_value_error():
    columns = [
        "time", "open", "high", "low", "close",
        "tick_volume", "spread", "real_volume",
        "auxiliary", "auxiliary", 7, 7,
    ]
    values = [[
        1_700_000_000, 1.1, 1.3, 1.0, 1.2,
        10, 2, 0, "first", "second", "left", "right",
    ]]
    rates = pd.DataFrame(values, columns=columns)

    with pytest.raises(ValueError, match="Duplicate market columns"):
        validate_rates(rates)