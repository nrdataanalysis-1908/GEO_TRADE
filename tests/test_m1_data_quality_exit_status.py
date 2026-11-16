from argparse import Namespace
from datetime import datetime, timezone
from types import SimpleNamespace

from src.ingestion import trade2_geo_trade_v2 as m1


class _Terminal:
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
        return [{
            "time": 1_762_147_260,
            "open": 1.1,
            "high": 1.3,
            "low": 1.0,
            "close": 1.2,
            "tick_volume": 10,
            "spread": 2,
            "real_volume": 0,
        }]

    def shutdown(self):
        return None


def _configure_main(monkeypatch, tmp_path, result):
    timestamp = datetime(2026, 11, 3, 3, 1, tzinfo=timezone.utc)
    monkeypatch.setattr(m1, "mt5", _Terminal())
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
    monkeypatch.setattr(m1, "gravar_candles", lambda *args: result(timestamp))


def test_m1_main_returns_nonzero_for_persisted_market_conflicts(monkeypatch, tmp_path, capsys):
    def conflict(timestamp):
        return {
            "encontrados": 1,
            "inseridos": 0,
            "rejeitados": 1,
            "conflitos_banco": 1,
            "primeiro": timestamp,
            "ultimo": timestamp,
            "maxima": 1.3,
            "minima": 1.0,
        }

    _configure_main(monkeypatch, tmp_path, conflict)

    assert m1.main() == 1
    output = capsys.readouterr().out
    assert "Conflitos com banco" in output
    assert "Conflitos persistidos" in output


def test_m1_main_returns_nonzero_when_every_returned_candle_is_rejected(monkeypatch, tmp_path, capsys):
    def all_rejected(timestamp):
        return {
            "encontrados": 0,
            "inseridos": 0,
            "rejeitados": 2,
            "conflitos_banco": 0,
            "primeiro": None,
            "ultimo": None,
            "maxima": None,
            "minima": None,
        }

    _configure_main(monkeypatch, tmp_path, all_rejected)

    assert m1.main() == 1
    output = capsys.readouterr().out
    assert "2 candles rejeitados" in output
    assert "Candles rejeitados" in output
