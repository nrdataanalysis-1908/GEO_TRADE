from datetime import datetime, timedelta, timezone

import pandas as pd

from src.ingestion import market_ingestion


class FakeMetaTrader:
    def __init__(self, rates):
        self.rates = rates
        self.request = None

    def symbol_select(self, symbol, enable):
        return True

    def copy_rates_range(self, symbol, timeframe, start, end):
        self.request = (symbol, timeframe, start, end)
        return self.rates


def _rate(timestamp):
    return {
        "time": int(timestamp.timestamp()),
        "open": 1.1000,
        "high": 1.1200,
        "low": 1.0900,
        "close": 1.1100,
        "tick_volume": 100,
        "spread": 2,
        "real_volume": 0,
    }


def test_collect_symbol_requests_fourteen_day_warmup_and_filters_requested_day(monkeypatch):
    start = datetime(2026, 11, 9, tzinfo=timezone.utc)
    end = start + timedelta(days=1)
    rates = [
        _rate(start - timedelta(hours=1)),
        _rate(start + timedelta(hours=1)),
        _rate(end),
    ]
    terminal = FakeMetaTrader(rates)
    monkeypatch.setattr(market_ingestion, "mt5", terminal)

    frame, rejected, error = market_ingestion.collect_symbol("EURUSD", start, end)

    assert error is None
    assert rejected == 0
    assert terminal.request == (
        "EURUSD",
        market_ingestion.TIMEFRAME,
        start - timedelta(days=14),
        end,
    )
    assert frame is not None
    assert frame["timestamp_utc"].tolist() == [pd.Timestamp(start + timedelta(hours=1))]

def test_collect_symbol_includes_start_and_excludes_end_boundary(monkeypatch):
    start = datetime(2026, 11, 9, tzinfo=timezone.utc)
    end = start + timedelta(days=1)
    terminal = FakeMetaTrader([_rate(start), _rate(end)])
    monkeypatch.setattr(market_ingestion, "mt5", terminal)

    frame, rejected, error = market_ingestion.collect_symbol("EURUSD", start, end)

    assert error is None
    assert rejected == 0
    assert frame is not None
    assert frame["timestamp_utc"].tolist() == [pd.Timestamp(start)]

