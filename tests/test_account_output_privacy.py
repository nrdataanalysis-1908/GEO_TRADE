from types import SimpleNamespace

import src.ingestion.market_ingestion as h1
import src.ingestion.trade2_geo_trade_v2 as m1


class _H1Terminal:
    def initialize(self, **kwargs):
        return True

    def account_info(self):
        return SimpleNamespace(login=987654321, server="private-h1-broker")

    def symbols_get(self):
        return []

    def shutdown(self):
        return None


class _M1Terminal:
    def initialize(self, **kwargs):
        return True

    def version(self):
        return (5, 0, 0)

    def account_info(self):
        return SimpleNamespace(
            server="private-m1-broker",
            currency="USD",
            balance=987654.32,
        )

    def symbols_get(self):
        return []

    def shutdown(self):
        return None

    def last_error(self):
        return (0, "ok")


def test_h1_console_omits_account_login_and_server(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(
        h1,
        "parse_args",
        lambda: SimpleNamespace(
            date="2026-11-03",
            symbols=None,
            terminal_path="fake-terminal",
            output_dir=tmp_path,
        ),
    )
    monkeypatch.setattr(h1, "mt5", _H1Terminal())

    assert h1.main() == 1

    output = capsys.readouterr().out
    assert "987654321" not in output
    assert "private-h1-broker" not in output
    assert "account details omitted" in output.lower()


def test_m1_console_omits_server_currency_and_balance(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(
        m1,
        "parse_args",
        lambda: SimpleNamespace(
            symbols=None,
            data_alvo="2026-11-03",
            terminal_path="fake-terminal",
            db_path=str(tmp_path / "market.db"),
            no_open_db=True,
        ),
    )
    monkeypatch.setattr(m1, "mt5", _M1Terminal())

    assert m1.main() == 1

    output = capsys.readouterr().out
    assert "private-m1-broker" not in output
    assert "987654.32" not in output
    assert "USD" not in output
    assert "dados da conta omitidos" in output.lower()
