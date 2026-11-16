from argparse import Namespace
from types import SimpleNamespace

import pytest

from src.ingestion import trade2_geo_trade_v2 as m1


class _Terminal:
    def __init__(self, selection_results, rate_results):
        self.selection_results = iter(selection_results)
        self.rate_results = iter(rate_results)

    def initialize(self, **kwargs):
        return True

    def version(self):
        return (5, 0, 0, 0, 0)

    def account_info(self):
        return SimpleNamespace()

    def symbols_get(self):
        return [SimpleNamespace(name="EURUSD"), SimpleNamespace(name="GBPUSD")]

    def symbol_select(self, symbol, selected):
        return next(self.selection_results)

    def copy_rates_range(self, *args):
        return next(self.rate_results)

    def last_error(self):
        return (0, "simulated")

    def shutdown(self):
        return None


def _run_main(monkeypatch, tmp_path, terminal):
    sleeps = []
    monkeypatch.setattr(m1, "mt5", terminal)
    monkeypatch.setattr(m1.time, "sleep", sleeps.append)
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
    result = m1.main()
    return result, sleeps


def test_m1_throttles_after_symbol_selection_failure(monkeypatch, tmp_path):
    terminal = _Terminal([False, True], [[]])

    result, sleeps = _run_main(monkeypatch, tmp_path, terminal)

    assert result == 1
    assert sleeps == [m1.PAUSA_ATIVO, m1.PAUSA_ATIVO]


def test_m1_throttles_after_missing_history_response(monkeypatch, tmp_path):
    terminal = _Terminal([True, True], [None, []])

    result, sleeps = _run_main(monkeypatch, tmp_path, terminal)

    assert result == 1
    assert sleeps == [m1.PAUSA_ATIVO, m1.PAUSA_ATIVO]
