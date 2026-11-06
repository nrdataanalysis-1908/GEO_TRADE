from datetime import datetime, timedelta, timezone

from src.ingestion.trade2_geo_trade_v2 import gravar_candles, preparar_banco


def _base_candle(timestamp):
    return {
        "time": timestamp,
        "open": 1.1,
        "high": 1.3,
        "low": 1.0,
        "close": 1.2,
        "tick_volume": 10,
        "spread": 2,
        "real_volume": 0,
    }


def _bounds(timestamp):
    start = datetime.fromtimestamp(timestamp, tz=timezone.utc)
    return start - timedelta(minutes=1), start + timedelta(minutes=1)


def test_identical_duplicate_m1_bars_are_collapsed(tmp_path):
    timestamp = 1_700_000_000
    database = preparar_banco(tmp_path / "market.db")
    try:
        result = gravar_candles(
            database.cursor(),
            "EURUSD",
            [_base_candle(timestamp), _base_candle(timestamp)],
            *_bounds(timestamp),
        )
        database.commit()

        total = database.execute("SELECT COUNT(*) FROM candles").fetchone()[0]
        assert result["encontrados"] == 1
        assert result["inseridos"] == 1
        assert result["rejeitados"] == 1
        assert total == 1
    finally:
        database.close()


def test_conflicting_duplicate_m1_bars_are_all_rejected(tmp_path):
    timestamp = 1_700_000_000
    first = _base_candle(timestamp)
    second = {**first, "close": 1.25}
    database = preparar_banco(tmp_path / "market.db")
    try:
        result = gravar_candles(
            database.cursor(),
            "EURUSD",
            [first, second],
            *_bounds(timestamp),
        )
        database.commit()

        total = database.execute("SELECT COUNT(*) FROM candles").fetchone()[0]
        assert result["encontrados"] == 0
        assert result["inseridos"] == 0
        assert result["rejeitados"] == 2
        assert total == 0
    finally:
        database.close()
