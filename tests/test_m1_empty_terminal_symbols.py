from types import SimpleNamespace

import src.ingestion.trade2_geo_trade_v2 as m1


class FakeConnection:
    def __init__(self):
        self.closed = False

    def cursor(self):
        return object()

    def close(self):
        self.closed = True


class EmptyTerminal:
    def __init__(self):
        self.shutdown_called = False

    def initialize(self, **kwargs):
        return True

    def version(self):
        return (1, 0, 0)

    def account_info(self):
        return SimpleNamespace(server="demo", currency="USD", balance=0)

    def symbols_get(self):
        return []

    def shutdown(self):
        self.shutdown_called = True


def test_main_fails_instead_of_reporting_success_when_terminal_has_no_symbols(monkeypatch, tmp_path):
    terminal = EmptyTerminal()
    connection = FakeConnection()
    monkeypatch.setattr(m1, "parse_args", lambda: SimpleNamespace(
        symbols=None, data_alvo="2026-11-03", terminal_path="fake-terminal",
        db_path=str(tmp_path / "empty.db"), no_open_db=True,
    ))
    monkeypatch.setattr(m1, "mt5", terminal)
    monkeypatch.setattr(m1, "preparar_banco", lambda path: connection)

    result = m1.main()

    assert result == 1
    assert connection.closed is True
    assert terminal.shutdown_called is True
