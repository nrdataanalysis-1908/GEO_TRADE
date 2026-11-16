from datetime import datetime, timedelta, timezone

import pytest

import src.ingestion.market_ingestion as h1
from src.ingestion.market_ingestion import collect_symbol


@pytest.mark.parametrize(
    "start,end",
    [
        (datetime(2026, 11, 3), datetime(2026, 11, 4, tzinfo=timezone.utc)),
        (
            datetime(2026, 11, 4, tzinfo=timezone.utc),
            datetime(2026, 11, 3, tzinfo=timezone.utc),
        ),
    ],
)
def test_collect_symbol_rejects_invalid_utc_bounds_before_mt5(monkeypatch, start, end):
    class UnexpectedTerminalCall:
        def symbol_select(self, *args):
            raise AssertionError("MT5 must not receive invalid date bounds")

    monkeypatch.setattr(h1, "mt5", UnexpectedTerminalCall())
    with pytest.raises(ValueError):
        collect_symbol("EURUSD", start, end)
