from argparse import Namespace
from types import SimpleNamespace

from src.ingestion import market_ingestion as h1
from test_features import sample_rates
from src.ingestion.market_ingestion import add_features


class _ShutdownFailingTerminal:
    def initialize(self, **kwargs):
        return True

    def account_info(self):
        return SimpleNamespace()

    def symbols_get(self):
        return [SimpleNamespace(name="EURUSD")]

    def shutdown(self):
        raise RuntimeError("simulated terminal shutdown failure")


def test_h1_main_returns_nonzero_when_terminal_shutdown_fails(monkeypatch, tmp_path):
    terminal = _ShutdownFailingTerminal()
    monkeypatch.setattr(h1, "mt5", terminal)
    monkeypatch.setattr(
        h1,
        "parse_args",
        lambda: Namespace(
            date="2026-11-03",
            symbols=None,
            terminal_path="unused",
            output_dir=tmp_path,
        ),
    )
    monkeypatch.setattr(
        h1,
        "collect_symbol",
        lambda symbol, start, end: (add_features(sample_rates(), symbol), 0, None),
    )

    assert h1.main() == 1
