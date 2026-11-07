import pytest

from src.ingestion.trade2_geo_trade_v2 import validar_simbolos


def test_validar_simbolos_preserves_valid_order():
    assert validar_simbolos(["EURUSD", "GBPUSD"]) == ["EURUSD", "GBPUSD"]
    assert validar_simbolos(None) is None


@pytest.mark.parametrize(
    "symbols",
    [
        ["EURUSD", "EURUSD"],
        [" EURUSD"],
        [""],
        [None],
    ],
)
def test_validar_simbolos_rejects_duplicates_and_malformed_names(symbols):
    with pytest.raises(ValueError):
        validar_simbolos(symbols)
