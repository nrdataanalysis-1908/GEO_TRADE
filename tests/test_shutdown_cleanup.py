from types import SimpleNamespace

import src.ingestion.market_ingestion as h1
import src.ingestion.trade2_geo_trade_v2 as m1


class FakeConnection:
    def cursor(self):
        return object()

    def close(self):
        return None


class M1Terminal:
    def initialize(self, **kwargs): return True
    def version(self): return (1, 0, 0)
    def account_info(self): return SimpleNamespace(server="demo", currency="USD", balance=0)
    def symbols_get(self): return []
    def shutdown(self): raise RuntimeError("simulated shutdown failure")


class H1Terminal:
    def initialize(self, **kwargs): return True
    def account_info(self): return SimpleNamespace(login=1, server="demo")
    def symbols_get(self): return [SimpleNamespace(name="EURUSD")]
    def shutdown(self): raise RuntimeError("simulated shutdown failure")


def test_m1_cleanup_failure_does_not_mask_extraction_result(monkeypatch, tmp_path):
    monkeypatch.setattr(m1, "parse_args", lambda: SimpleNamespace(
        symbols=None, data_alvo="2026-11-03", terminal_path="fake",
        db_path=str(tmp_path / "m1.db"), no_open_db=True,
    ))
    monkeypatch.setattr(m1, "mt5", M1Terminal())
    monkeypatch.setattr(m1, "preparar_banco", lambda path: FakeConnection())

    assert m1.main() == 1


def test_h1_shutdown_failure_does_not_mask_no_data_result(monkeypatch, tmp_path):
    monkeypatch.setattr(h1, "parse_args", lambda: SimpleNamespace(
        symbols=None, date="2026-11-03", terminal_path="fake", output_dir=tmp_path,
    ))
    monkeypatch.setattr(h1, "mt5", H1Terminal())
    monkeypatch.setattr(h1, "collect_symbol", lambda symbol, start, end: (None, 0, None))

    assert h1.main() == 1
