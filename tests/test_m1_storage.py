from datetime import date, datetime, timedelta, timezone

import pytest
import numpy as np

from src.ingestion.trade2_geo_trade_v2 import (
    FUSO_BRASILIA,
    gravar_candles,
    gravar_metadados_ativo,
    obter_intervalo_utc,
    preparar_banco,
    validar_candle,
)



@pytest.mark.parametrize(
    "field",
    ["time", "open", "high", "low", "close", "tick_volume", "spread", "real_volume"],
)
def test_candle_rejects_numpy_boolean_market_values(field):
    candle = {
        "time": 1_700_000_000,
        "open": 1.1, "high": 1.3, "low": 1.0, "close": 1.2,
        "tick_volume": 10, "spread": 2, "real_volume": 0,
    }
    candle[field] = np.bool_(True)
    assert validar_candle(candle) is False



def test_candle_rejects_counters_outside_sqlite_integer_range():
    base = {
        "time": 1_700_000_000,
        "open": 1.1, "high": 1.3, "low": 1.0, "close": 1.2,
        "tick_volume": 10, "spread": 2, "real_volume": 0,
    }
    for field in ("tick_volume", "spread", "real_volume"):
        candidate = {**base, field: 2**63}
        assert validar_candle(candidate) is False


def test_candle_accepts_sqlite_signed_integer_upper_bound():
    candle = {
        "time": 1_700_000_000,
        "open": 1.1, "high": 1.3, "low": 1.0, "close": 1.2,
        "tick_volume": 2**63 - 1, "spread": 2, "real_volume": 0,
    }
    assert validar_candle(candle) is True


def test_integral_numeric_strings_are_validated_and_persisted_consistently(tmp_path):
    database = preparar_banco(tmp_path / "numeric-strings.db")
    try:
        start = datetime(2023, 11, 14, tzinfo=timezone.utc)
        end = start + timedelta(days=1)
        candle = {
            "time": "1700000000.0",
            "open": "1.1", "high": "1.3", "low": "1.0", "close": "1.2",
            "tick_volume": "10.0", "spread": "2.0", "real_volume": "0.0",
        }

        assert validar_candle(candle) is True
        result = gravar_candles(database.cursor(), "EURUSD", [candle], start, end)
        database.commit()
        persisted = database.execute(
            "SELECT tick_volume, spread, real_volume FROM candles"
        ).fetchone()

        assert result["inseridos"] == 1
        assert tuple(persisted) == (10, 2, 0)
    finally:
        database.close()


def test_candle_rejects_scientific_counter_overflow_without_raising():
    candle = {
        "time": 1_700_000_000,
        "open": 1.1, "high": 1.3, "low": 1.0, "close": 1.2,
        "tick_volume": "1e308", "spread": 2, "real_volume": 0,
    }
    assert validar_candle(candle) is False


def test_asset_created_at_preserves_initial_registration_timestamp(tmp_path):
    from types import SimpleNamespace

    database = preparar_banco(tmp_path / "metadata.db")
    try:
        cursor = database.cursor()
        gravar_metadados_ativo(
            cursor, SimpleNamespace(name="EURUSD", description="initial")
        )
        database.commit()
        original_timestamp = "2020-01-01T00:00:00+00:00"
        database.execute(
            "UPDATE ativos SET created_at = ? WHERE symbol = ?",
            (original_timestamp, "EURUSD"),
        )
        database.commit()

        gravar_metadados_ativo(
            cursor, SimpleNamespace(name="EURUSD", description="refreshed")
        )
        database.commit()
        row = database.execute(
            "SELECT created_at, description FROM ativos WHERE symbol = ?",
            ("EURUSD",),
        ).fetchone()

        assert row["created_at"] == original_timestamp
        assert row["description"] == "refreshed"
    finally:
        database.close()


def test_candle_persistence_preserves_sqlite_signed_integer_upper_bound(tmp_path):
    database = preparar_banco(tmp_path / "integer-bound.db")
    try:
        start = datetime(2023, 11, 14, tzinfo=timezone.utc)
        end = start + timedelta(days=1)
        candle = {
            "time": 1_700_000_000,
            "open": 1.1, "high": 1.3, "low": 1.0, "close": 1.2,
            "tick_volume": 2**63 - 1, "spread": 2, "real_volume": 0,
        }
        result = gravar_candles(
            database.cursor(), "EURUSD", [candle], start, end
        )
        database.commit()
        persisted = database.execute(
            "SELECT tick_volume FROM candles"
        ).fetchone()[0]

        assert result["inseridos"] == 1
        assert persisted == 2**63 - 1
    finally:
        database.close()


def test_brasilia_calendar_day_is_converted_to_utc():
    selected, start, end = obter_intervalo_utc("2026-11-03")

    assert selected == date(2026, 11, 3)
    assert start == datetime(2026, 11, 3, 3, tzinfo=timezone.utc)
    assert end == datetime(2026, 11, 4, 3, tzinfo=timezone.utc)
    assert end - start == timedelta(days=1)


def test_candle_persistence_is_idempotent_and_excludes_end_boundary(tmp_path):
    database = preparar_banco(tmp_path / "market.db")
    try:
        start = datetime(2026, 11, 3, 3, tzinfo=timezone.utc)
        end = start + timedelta(days=1)
        rates = [
            {
                "time": int((start + timedelta(minutes=1)).timestamp()),
                "open": 1.1, "high": 1.3, "low": 1.0, "close": 1.2,
                "tick_volume": 10, "spread": 2, "real_volume": 0,
            },
            {
                "time": int(end.timestamp()),
                "open": 1.2, "high": 1.4, "low": 1.1, "close": 1.3,
                "tick_volume": 11, "spread": 2, "real_volume": 0,
            },
        ]

        first = gravar_candles(database.cursor(), "EURUSD", rates, start, end)
        database.commit()
        second = gravar_candles(database.cursor(), "EURUSD", rates, start, end)
        database.commit()

        total = database.execute("SELECT COUNT(*) FROM candles").fetchone()[0]
        local_timestamp = database.execute(
            "SELECT timestamp_brasilia FROM candles"
        ).fetchone()[0]

        assert first["encontrados"] == 1
        assert first["inseridos"] == 1
        assert second["encontrados"] == 1
        assert second["inseridos"] == 0
        assert total == 1
        assert datetime.fromisoformat(local_timestamp).utcoffset() == timedelta(hours=-3)
    finally:
        database.close()



def test_valid_candle_passes_quality_gate():
    candle = {
        "time": 1_700_000_000,
        "open": 1.1, "high": 1.3, "low": 1.0, "close": 1.2,
        "tick_volume": 10, "spread": 2, "real_volume": 0,
    }
    assert validar_candle(candle) is True


def test_invalid_ohlc_relationship_is_rejected():
    candle = {
        "time": 1_700_000_000,
        "open": 1.1, "high": 1.05, "low": 1.0, "close": 1.2,
        "tick_volume": 10, "spread": 2, "real_volume": 0,
    }
    assert validar_candle(candle) is False


def test_non_finite_price_is_rejected():
    candle = {
        "time": 1_700_000_000,
        "open": 1.1, "high": float("nan"), "low": 1.0, "close": 1.2,
        "tick_volume": 10, "spread": 2, "real_volume": 0,
    }
    assert validar_candle(candle) is False


def test_negative_volume_or_spread_is_rejected():
    candle = {
        "time": 1_700_000_000,
        "open": 1.1, "high": 1.3, "low": 1.0, "close": 1.2,
        "tick_volume": -1, "spread": 2, "real_volume": 0,
    }
    assert validar_candle(candle) is False


def test_missing_market_field_is_rejected():
    candle = {
        "time": 1_700_000_000,
        "open": 1.1, "high": 1.3, "low": 1.0, "close": 1.2,
        "tick_volume": 10, "spread": 2,
    }
    assert validar_candle(candle) is False

def test_candle_requires_a_finite_integral_timestamp():
    candle = {
        "time": float("nan"),
        "open": 1.1, "high": 1.3, "low": 1.0, "close": 1.2,
        "tick_volume": 10, "spread": 2, "real_volume": 0,
    }
    assert validar_candle(candle) is False
    candle.pop("time")
    assert validar_candle(candle) is False


def test_candle_rejects_fractional_or_negative_counters():
    base = {
        "time": 1_700_000_000,
        "open": 1.1, "high": 1.3, "low": 1.0, "close": 1.2,
        "tick_volume": 10, "spread": 2, "real_volume": 0,
    }
    for field, value in (("tick_volume", 1.5), ("spread", -1), ("real_volume", float("inf"))):
        candidate = {**base, field: value}
        assert validar_candle(candidate) is False

@pytest.mark.parametrize("field", ["open", "high", "low", "close"])
def test_candle_rejects_boolean_price_fields(field):
    candle = {
        "time": 1_700_000_000,
        "open": 1.1, "high": 1.3, "low": 1.0, "close": 1.2,
        "tick_volume": 10, "spread": 2, "real_volume": 0,
    }
    candle[field] = True
    assert validar_candle(candle) is False

@pytest.mark.parametrize("field", ["time", "tick_volume", "spread", "real_volume"])
def test_candle_rejects_boolean_timestamp_and_counters(field):
    candle = {
        "time": 1_700_000_000,
        "open": 1.1, "high": 1.3, "low": 1.0, "close": 1.2,
        "tick_volume": 10, "spread": 2, "real_volume": 0,
    }
    candle[field] = True
    assert validar_candle(candle) is False

@pytest.mark.parametrize("value", ["2026-W45-3", "20261104", "04-11-2026"])
def test_brasilia_date_parser_rejects_non_calendar_formats(value):
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        obter_intervalo_utc(value)
