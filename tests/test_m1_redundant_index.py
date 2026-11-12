import sqlite3

from src.ingestion.trade2_geo_trade_v2 import preparar_banco


def test_symbol_prefix_index_replaces_redundant_single_column_index(tmp_path):
    database = preparar_banco(tmp_path / "indexes.db")
    try:
        indexes = {row[1] for row in database.execute("PRAGMA index_list(candles)")}
        assert "idx_candles_symbol_time" in indexes
        assert "idx_candles_symbol" not in indexes
    finally:
        database.close()


def test_existing_database_drops_redundant_symbol_index_without_losing_rows(tmp_path):
    path = tmp_path / "legacy-index.db"
    legacy = sqlite3.connect(path)
    legacy.execute("CREATE TABLE candles (symbol TEXT, timestamp_utc TEXT)")
    legacy.execute("CREATE INDEX idx_candles_symbol ON candles(symbol)")
    legacy.execute("INSERT INTO candles VALUES ('EURUSD', '2026-11-03T00:00:00+00:00')")
    legacy.commit()
    legacy.close()

    database = preparar_banco(path)
    try:
        indexes = {row[1] for row in database.execute("PRAGMA index_list(candles)")}
        row = database.execute("SELECT symbol FROM candles").fetchone()
        assert "idx_candles_symbol" not in indexes
        assert row == ("EURUSD",)
    finally:
        database.close()
