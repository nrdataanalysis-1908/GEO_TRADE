from argparse import Namespace
from types import SimpleNamespace

from src.ingestion import trade2_geo_trade_v2 as m1


class _ShutdownFailingTerminal:
    def initialize(self, **kwargs):
        return True

    def version(self):
        return (5, 0, 0, 0, 0)

    def account_info(self):
        return SimpleNamespace()

    def symbols_get(self):
        return [SimpleNamespace(name="EURUSD")]

    def symbol_select(self, symbol, selected):
        return True

    def copy_rates_range(self, *args):
        return []

    def shutdown(self):
        raise RuntimeError("simulated terminal shutdown failure")


def test_m1_main_returns_nonzero_when_terminal_shutdown_fails(
    monkeypatch, tmp_path
):
    terminal = _ShutdownFailingTerminal()
    monkeypatch.setattr(m1, "mt5", terminal)
    monkeypatch.setattr(m1.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(
        m1,
        "parse_args",
        lambda: Namespace(
            data_alvo="2026-11-03",
            terminal_path="unused",
            db_path=str(tmp_path / "market.db"),
            symbols=None,
            no_open_db=True,
        ),
    )

    assert m1.main() == 1



class _NormalTerminal:
    def initialize(self, **kwargs):
        return True

    def version(self):
        return (5, 0, 0, 0, 0)

    def account_info(self):
        return SimpleNamespace()

    def symbols_get(self):
        return [SimpleNamespace(name="EURUSD")]

    def symbol_select(self, symbol, selected):
        return True

    def copy_rates_range(self, *args):
        return []

    def shutdown(self):
        return None


def test_m1_main_does_not_open_db_browser_after_sqlite_close_failure(
    monkeypatch, tmp_path
):
    terminal = _NormalTerminal()
    original_prepare = m1.preparar_banco
    opened = []

    class _CloseFailingConnection:
        def __init__(self, connection):
            self.connection = connection

        def __getattr__(self, name):
            return getattr(self.connection, name)

        def close(self):
            self.connection.close()
            raise RuntimeError("simulated SQLite close failure")

    monkeypatch.setattr(m1, "mt5", terminal)
    monkeypatch.setattr(m1.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(
        m1,
        "parse_args",
        lambda: Namespace(
            data_alvo="2026-11-03",
            terminal_path="unused",
            db_path=str(tmp_path / "market.db"),
            symbols=None,
            no_open_db=False,
        ),
    )
    monkeypatch.setattr(
        m1,
        "preparar_banco",
        lambda path: _CloseFailingConnection(original_prepare(path)),
    )
    monkeypatch.setattr(m1, "abrir_db_browser", lambda path: opened.append(path))

    assert m1.main() == 1
    assert opened == []


def test_m1_main_returns_nonzero_when_sqlite_close_fails(
    monkeypatch, tmp_path
):
    terminal = _NormalTerminal()
    original_prepare = m1.preparar_banco

    class _CloseFailingConnection:
        def __init__(self, connection):
            self.connection = connection

        def __getattr__(self, name):
            return getattr(self.connection, name)

        def close(self):
            self.connection.close()
            raise RuntimeError("simulated SQLite close failure")

    monkeypatch.setattr(m1, "mt5", terminal)
    monkeypatch.setattr(m1.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(
        m1,
        "parse_args",
        lambda: Namespace(
            data_alvo="2026-11-03",
            terminal_path="unused",
            db_path=str(tmp_path / "market.db"),
            symbols=None,
            no_open_db=True,
        ),
    )
    monkeypatch.setattr(
        m1,
        "preparar_banco",
        lambda path: _CloseFailingConnection(original_prepare(path)),
    )

    assert m1.main() == 1
