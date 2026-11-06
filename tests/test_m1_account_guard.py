from argparse import Namespace

import src.ingestion.trade2_geo_trade_v2 as m1


class UnauthenticatedTerminal:
    def __init__(self):
        self.shutdown_called = False

    def initialize(self, **kwargs):
        return True

    def version(self):
        return (5, 0, 0, 0, 0)

    def account_info(self):
        return None

    def last_error(self):
        return (100, "account is not authenticated")

    def symbols_get(self):
        return []

    def shutdown(self):
        self.shutdown_called = True


def test_m1_main_stops_before_database_creation_without_authenticated_account(tmp_path, monkeypatch):
    terminal = UnauthenticatedTerminal()
    database = tmp_path / "market.db"
    monkeypatch.setattr(m1, "mt5", terminal)
    monkeypatch.setattr(
        m1,
        "parse_args",
        lambda: Namespace(
            data_alvo="2026-11-05",
            terminal_path="terminal64.exe",
            db_path=str(database),
            symbols=None,
            no_open_db=True,
        ),
    )

    result = m1.main()

    assert result == 1
    assert not database.exists()
    assert terminal.shutdown_called
