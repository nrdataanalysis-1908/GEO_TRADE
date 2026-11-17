from argparse import Namespace
from types import SimpleNamespace

import src.ingestion.trade2_geo_trade_v2 as m1


class _Terminal:
    def __init__(self):
        self.shutdown_called = False

    def initialize(self, **kwargs):
        return True

    def version(self):
        return (5, 0, 0, 0, 0)

    def account_info(self):
        return SimpleNamespace()

    def shutdown(self):
        self.shutdown_called = True


def test_main_rejects_database_symlink_without_touching_target(monkeypatch, tmp_path):
    target = tmp_path / "external.db"
    sentinel = b"do-not-modify-this-file"
    target.write_bytes(sentinel)
    link = tmp_path / "market.db"
    link.symlink_to(target)
    terminal = _Terminal()

    monkeypatch.setattr(m1, "mt5", terminal)
    monkeypatch.setattr(
        m1,
        "parse_args",
        lambda: Namespace(
            data_alvo="2026-11-03",
            terminal_path="unused",
            db_path=str(link),
            symbols=None,
            no_open_db=True,
        ),
    )

    assert m1.main() == 1
    assert target.read_bytes() == sentinel
    assert terminal.shutdown_called