from datetime import datetime, timedelta, timezone

from src.ingestion.trade2_geo_trade_v2 import gravar_candles, preparar_banco


def _candle(timestamp, close):
    return {
        "time": timestamp,
        "open": 1.1,
        "high": 1.3,
        "low": 1.0,
        "close": close,
        "tick_volume": 10,
        "spread": 2,
        "real_volume": 0,
    }


def test_existing_timestamp_with_changed_market_values_is_reported_not_overwritten(tmp_path):
    database = preparar_banco(tmp_path / "market.db")
    try:
        start = datetime(2026, 11, 3, 3, tzinfo=timezone.utc)
        end = start + timedelta(days=1)
        timestamp = int((start + timedelta(minutes=1)).timestamp())

        first = gravar_candles(database.cursor(), "EURUSD", [_candle(timestamp, 1.2)], start, end)
        database.commit()
        second = gravar_candles(database.cursor(), "EURUSD", [_candle(timestamp, 1.25)], start, end)
        database.commit()

        stored = database.execute(
            "SELECT close FROM candles WHERE symbol = ?",
            ("EURUSD",),
        ).fetchone()[0]

        assert first["inseridos"] == 1
        assert second["inseridos"] == 0
        assert second["conflitos_banco"] == 1
        assert second["rejeitados"] == 1
        assert stored == 1.2
    finally:
        database.close()
