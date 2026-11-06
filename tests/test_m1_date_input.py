import pytest

from src.ingestion.trade2_geo_trade_v2 import obter_intervalo_utc


@pytest.mark.parametrize("value", ["", 0, False, []])
def test_explicit_empty_or_false_date_values_are_not_treated_as_default(value):
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        obter_intervalo_utc(value)


def test_none_remains_the_only_default_date_signal():
    selected, start, end = obter_intervalo_utc(None)
    assert end - start == __import__("datetime").timedelta(days=1)
    assert selected.isoformat() == start.astimezone(__import__("datetime").timezone(
        __import__("datetime").timedelta(hours=-3)
    )).date().isoformat()
