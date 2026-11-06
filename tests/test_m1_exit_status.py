from argparse import Namespace
from types import SimpleNamespace

import src.ingestion.trade2_geo_trade_v2 as m1


class FailingMarketTerminal:
    def __init__(self):
        self.shutdown_called = False

    def initialize(self, **kwargs):
        return True

    def version(self):
        return (5, 0, 0, 0, 0)

    def account_info(self):
        return SimpleNamespace(server="Demo", currency="USD", balance=1000)

    def symbols_get(self):
        return [SimpleNamespace(name="EURUSD")]

    def symbol_select(self, symbol, selected):
        return True

    def copy_rates_range(self, *args):
        raise RuntimeError("simulated history transport failure")

    def last_error(self):
        return (1, "simulated failure")

    def shutdown(self):
        self.shutdown_called = True


def test_m1_main_returns_nonzero_when_any_symbol_fails(tmp_path, monkeypatch):
    terminal = FailingMarketTerminal()
    monkeypatch.setattr(m1, "mt5", terminal)
    monkeypatch.setattr(m1.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(
        m1,
        "parse_args",
        lambda: Namespace(
            data_alvo="2026-11-05",
            terminal_path="terminal64.exe",
            db_path=str(tmp_path / "market.db"),
            symbols=None,
            no_open_db=True,
        ),
    )

    result = m1.main()

    assert result == 1
    assert terminal.shutdown_called
