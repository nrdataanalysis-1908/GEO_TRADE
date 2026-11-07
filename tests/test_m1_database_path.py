from src.ingestion.trade2_geo_trade_v2 import preparar_banco


def test_preparar_banco_accepts_string_paths(tmp_path):
    database_path = str(tmp_path / "nested" / "market.db")

    connection = preparar_banco(database_path)
    try:
        assert connection.execute("SELECT COUNT(*) FROM candles").fetchone()[0] == 0
    finally:
        connection.close()
