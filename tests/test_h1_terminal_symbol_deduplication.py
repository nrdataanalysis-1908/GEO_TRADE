from argparse import Namespace
from types import SimpleNamespace

import numpy as np
import pandas as pd

from src.ingestion import market_ingestion as h1
from src.ingestion.market_ingestion import add_features


class _DuplicateSymbolTerminal:
    def initialize(self, **kwargs):
        return True

    def account_info(self):
        return SimpleNamespace()

    def symbols_get(self):
        return [
            SimpleNamespace(name="EURUSD"),
            SimpleNamespace(name="EURUSD"),
            SimpleNamespace(name="GBPUSD"),
        ]

    def shutdown(self):
        return None


def _rates():
    return pd.DataFrame({
        "time": np.arange(1_700_000_000, 1_700_000_000 + 20 * 3600, 3600),
        "open": np.linspace(1.0, 1.02, 20),
        "high": np.linspace(1.01, 1.03, 20),
        "low": np.linspace(0.99, 1.01, 20),
        "close": np.linspace(1.005, 1.025, 20),
        "tick_volume": np.full(20, 100),
        "spread": np.full(20, 2),
        "real_volume": np.zeros(20),
    })


def test_h1_main_deduplicates_terminal_symbols_before_market_requests(monkeypatch, tmp_path):
    calls = []
    terminal = _DuplicateSymbolTerminal()

    def collect(symbol, start, end):
        calls.append(symbol)
        return add_features(_rates(), symbol), 0, None

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
    monkeypatch.setattr(h1, "collect_symbol", collect)

    assert h1.main() == 0
    assert calls == ["EURUSD", "GBPUSD"]
    assert len(list(tmp_path.glob("GEO_TRADE_MARKET_H1_DAY_20261103_*.csv"))) == 1
