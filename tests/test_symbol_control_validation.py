from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

import src.ingestion.market_ingestion as h1
from src.ingestion.market_ingestion import add_features, collect_symbol, validate_symbols
from src.ingestion.trade2_geo_trade_v2 import (
    gravar_candles, gravar_metadados_ativo, validar_simbolos,
)
from test_features import sample_rates


@pytest.mark.parametrize("symbol", ["EUR\\u0085USD", "EUR\\u009fUSD"])
def test_h1_rejects_unicode_control_characters(symbol):
    with pytest.raises(ValueError):
        validate_symbols([symbol])
    with pytest.raises(ValueError):
        add_features(sample_rates(), symbol)


@pytest.mark.parametrize("symbol", ["EUR\\u0085USD", "EUR\\u009fUSD"])
def test_m1_rejects_unicode_control_characters(symbol):
    with pytest.raises(ValueError):
        validar_simbolos([symbol])
    start = datetime(2026, 11, 3, tzinfo=timezone.utc)
    with pytest.raises(ValueError, match="valid trimmed name"):
        gravar_candles(None, symbol, [], start, start + timedelta(days=1))
    with pytest.raises(ValueError, match="valid symbol"):
        gravar_metadados_ativo(None, SimpleNamespace(name=symbol))


def test_h1_collect_symbol_rejects_invalid_name_before_mt5_call(monkeypatch):
    class UnexpectedTerminalCall:
        def symbol_select(self, *args):
            raise AssertionError("MT5 must not receive malformed symbols")

    monkeypatch.setattr(h1, "mt5", UnexpectedTerminalCall())
    start = datetime(2026, 11, 3, tzinfo=timezone.utc)
    with pytest.raises(ValueError):
        collect_symbol("EUR\\u0085USD", start, start + timedelta(hours=1))
