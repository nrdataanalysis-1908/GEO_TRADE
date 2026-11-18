from datetime import timedelta

import pytest

from src.ingestion.market_ingestion import utc_bounds


def test_utc_bounds_preserve_a_leap_day_as_one_full_utc_day():
    start, end = utc_bounds("2024-02-29")

    assert end - start == timedelta(days=1)
    assert start.isoformat() == "2024-02-29T00:00:00+00:00"
    assert end.isoformat() == "2024-03-01T00:00:00+00:00"


@pytest.mark.parametrize("value", ["2023-02-29", "2026-13-01", "0000-01-01"])
def test_utc_bounds_reject_nonexistent_calendar_dates(value):
    with pytest.raises(ValueError):
        utc_bounds(value)


def test_utc_bounds_rejects_a_date_without_an_exclusive_next_day():
    with pytest.raises(ValueError, match="exclusive next-day"):
        utc_bounds("9999-12-31")
