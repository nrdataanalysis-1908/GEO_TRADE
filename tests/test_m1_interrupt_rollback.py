import sqlite3
from argparse import Namespace
from types import SimpleNamespace

from src.ingestion import trade2_geo_trade_v2 as m1


def test_keyboard_interrupt_rolls_back_the_in_flight_symbol(tmp_path, monkeypatch):
    database = tmp_path / "market.db"
    fake_mt5 = SimpleNamespace(
        initialize=lambda **kwargs: True,
        version=lambda: (1, 0, 0),
        account_info=lambda: SimpleNamespace(server="test", currency="USD", balance=1000),
        symbol_info=lambda name: SimpleNamespace(name=name),
        symbol_select=lambda *args: True,
        copy_rates_range=lambda *args: [{}],
        last_error=lambda: "simulated",
        shutdown=lambda: None,
    )
    monkeypatch.setattr(m1, "mt5", fake_mt5)
    monkeypatch.setattr(
        m1, "parse_args",
        lambda: Namespace(
            data_alvo="2026-11-03",
            db_path=str(database),
            terminal_path="unused",
            symbols=["EURUSD"],
            no_open_db=True,
        ),
    )

    def interrupt_after_partial_write(cursor, symbol, rates, start, end):
        cursor.execute(
            """INSERT INTO candles(
                timestamp_utc, timestamp_brasilia, symbol, timeframe,
                open, high, low, close, tick_volume, spread, real_volume
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            ("2026-11-03T03:01:00+00:00", "2026-11-03T00:01:00-03:00",
             symbol, "M1", 1.1, 1.3, 1.0, 1.2, 10, 2, 0),
        )
        raise KeyboardInterrupt

    monkeypatch.setattr(m1, "gravar_candles", interrupt_after_partial_write)

    assert m1.main() == 130

    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT COUNT(*) FROM candles").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM ativos").fetchone()[0] == 0
