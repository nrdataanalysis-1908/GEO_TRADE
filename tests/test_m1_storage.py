from datetime import date, datetime, timedelta, timezone

from src.ingestion.trade2_geo_trade_v2 import (
    FUSO_BRASILIA,
    gravar_candles,
    obter_intervalo_utc,
    preparar_banco,
)


def test_brasilia_calendar_day_is_converted_to_utc():
    selected, start, end = obter_intervalo_utc("2026-11-03")

    assert selected == date(2026, 11, 3)
    assert start == datetime(2026, 11, 3, 3, tzinfo=timezone.utc)
    assert end == datetime(2026, 11, 4, 3, tzinfo=timezone.utc)
    assert end - start == timedelta(days=1)


def test_candle_persistence_is_idempotent_and_excludes_end_boundary(tmp_path):
    database = preparar_banco(tmp_path / "market.db")
    try:
        start = datetime(2026, 11, 3, 3, tzinfo=timezone.utc)
        end = start + timedelta(days=1)
        rates = [
            {
                "time": int((start + timedelta(minutes=1)).timestamp()),
                "open": 1.1, "high": 1.3, "low": 1.0, "close": 1.2,
                "tick_volume": 10, "spread": 2, "real_volume": 0,
            },
            {
                "time": int(end.timestamp()),
                "open": 1.2, "high": 1.4, "low": 1.1, "close": 1.3,
                "tick_volume": 11, "spread": 2, "real_volume": 0,
            },
        ]

        first = gravar_candles(database.cursor(), "EURUSD", rates, start, end)
        database.commit()
        second = gravar_candles(database.cursor(), "EURUSD", rates, start, end)
        database.commit()

        total = database.execute("SELECT COUNT(*) FROM candles").fetchone()[0]
        local_timestamp = database.execute(
            "SELECT timestamp_brasilia FROM candles"
        ).fetchone()[0]

        assert first["encontrados"] == 1
        assert first["inseridos"] == 1
        assert second["encontrados"] == 1
        assert second["inseridos"] == 0
        assert total == 1
        assert datetime.fromisoformat(local_timestamp).utcoffset() == timedelta(hours=-3)
    finally:
        database.close()
