from datetime import datetime, timedelta, timezone

import pytest

from src.ingestion.trade2_geo_trade_v2 import obter_intervalo_utc


@pytest.mark.parametrize(
    ("requested_date", "expected_start", "expected_end", "expected_hours"),
    [
        (
            "2018-11-04",
            datetime(2018, 11, 4, 3, tzinfo=timezone.utc),
            datetime(2018, 11, 5, 2, tzinfo=timezone.utc),
            23,
        ),
        (
            "2019-02-16",
            datetime(2019, 2, 16, 2, tzinfo=timezone.utc),
            datetime(2019, 2, 17, 3, tzinfo=timezone.utc),
            25,
        ),
    ],
)
def test_brasilia_calendar_day_respects_historical_dst(
    requested_date, expected_start, expected_end, expected_hours
):
    _, start, end = obter_intervalo_utc(requested_date)

    assert start == expected_start
    assert end == expected_end
    assert end - start == timedelta(hours=expected_hours)
