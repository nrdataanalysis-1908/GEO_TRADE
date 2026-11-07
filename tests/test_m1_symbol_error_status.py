from argparse import Namespace
from types import SimpleNamespace

import pytest

from src.ingestion import trade2_geo_trade_v2 as m1


def _run_main(tmp_path, monkeypatch, *, missing=False, selection_fails=False, rates_none=False):
    database = tmp_path / "market.db"
    fake_mt5 = SimpleNamespace(
        initialize=lambda **kwargs: True,
        version=lambda: (1, 0, 0),
        account_info=lambda: SimpleNamespace(server="test", currency="USD", balance=1000),
        symbol_info=lambda name: None if missing and name == "MISSING" else SimpleNamespace(name=name),
        symbol_select=lambda *args: not selection_fails,
        copy_rates_range=lambda *args: None if rates_none else [],
        last_error=lambda: "simulated MT5 error",
        shutdown=lambda: None,
    )
    monkeypatch.setattr(m1, "mt5", fake_mt5)
    monkeypatch.setattr(
        m1, "parse_args",
        lambda: Namespace(
            data_alvo="2026-11-03",
            db_path=str(database),
            terminal_path="unused",
            symbols=["MISSING", "EURUSD"] if missing else ["EURUSD"],
            no_open_db=True,
        ),
    )
    monkeypatch.setattr(m1.time, "sleep", lambda *_: None)
    return m1.main()


@pytest.mark.parametrize(
    "options",
    [
        {"missing": True, "selection_fails": True},
        {"rates_none": True},
    ],
)
def test_mt5_symbol_and_history_errors_produce_nonzero_exit(tmp_path, monkeypatch, options):
    assert _run_main(tmp_path, monkeypatch, **options) == 1
