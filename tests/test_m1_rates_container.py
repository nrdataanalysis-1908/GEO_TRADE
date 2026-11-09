from datetime import datetime, timedelta, timezone

import pytest

from src.ingestion.trade2_geo_trade_v2 import gravar_candles


@pytest.mark.parametrize("rates", ["not-a-record-list", b"binary-data", {"time": 1}, 42])
def test_m1_rejects_invalid_rate_containers_before_iteration(rates):
    start = datetime(2026, 11, 3, tzinfo=timezone.utc)
    with pytest.raises(ValueError, match="iterable of candle records"):
        gravar_candles(None, "EURUSD", rates, start, start + timedelta(days=1))
