from datetime import datetime, timedelta, timezone

import pytest

from src.ingestion.trade2_geo_trade_v2 import gravar_candles, preparar_banco


@pytest.mark.parametrize("symbol", ["", "   ", None])
def test_m1_persistence_rejects_empty_symbol(tmp_path, symbol):
    database = preparar_banco(tmp_path / "market.db")
    start = datetime(2026, 11, 3, tzinfo=timezone.utc)
    try:
        with pytest.raises(ValueError, match="symbol"):
            gravar_candles(database.cursor(), symbol, [], start, start + timedelta(days=1))
    finally:
        database.close()


def test_m1_persistence_requires_utc_aware_ordered_bounds(tmp_path):
    database = preparar_banco(tmp_path / "market.db")
    start = datetime(2026, 11, 3, tzinfo=timezone.utc)
    try:
        with pytest.raises(ValueError, match="UTC-aware"):
            gravar_candles(
                database.cursor(),
                "EURUSD",
                [],
                datetime(2026, 11, 3),
                start + timedelta(days=1),
            )
        with pytest.raises(ValueError, match="later than"):
            gravar_candles(
                database.cursor(),
                "EURUSD",
                [],
                start + timedelta(days=1),
                start,
            )
    finally:
        database.close()


def test_m1_persistence_rejects_missing_rate_collection(tmp_path):
    database = preparar_banco(tmp_path / "market.db")
    start = datetime(2026, 11, 3, tzinfo=timezone.utc)
    try:
        with pytest.raises(ValueError, match="rates"):
            gravar_candles(
                database.cursor(),
                "EURUSD",
                None,
                start,
                start + timedelta(days=1),
            )
    finally:
        database.close()
