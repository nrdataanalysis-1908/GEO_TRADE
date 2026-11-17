from types import SimpleNamespace

import numpy as np
import pytest

from src.ingestion.trade2_geo_trade_v2 import (
    gravar_metadados_ativo,
    preparar_banco,
    validar_candle,
)


def _candle():
    return {
        "time": 1_700_000_000,
        "open": 1.1, "high": 1.3, "low": 1.0, "close": 1.2,
        "tick_volume": 10, "spread": 2, "real_volume": 0,
    }


@pytest.mark.parametrize("field", ["open", "high", "low", "close"])
def test_validar_candle_rejects_numpy_complex_price_values(field):
    candle = _candle()
    candle[field] = np.complex64(1.1 + 0.2j)

    assert validar_candle(candle) is False


@pytest.mark.parametrize(
    "field",
    ["point", "trade_tick_size", "trade_tick_value", "volume_min", "volume_max", "volume_step"],
)
def test_asset_metadata_rejects_numpy_complex_numeric_values(tmp_path, field):
    database = preparar_banco(tmp_path / "complex-metadata.db")
    try:
        values = {
            "name": "EURUSD",
            "digits": 5,
            "point": 0.00001,
            "trade_tick_size": 0.00001,
            "trade_tick_value": 1.0,
            "volume_min": 0.01,
            "volume_max": 1.0,
            "volume_step": 0.01,
        }
        values[field] = np.complex64(1.0 + 0.5j)

        with pytest.raises(ValueError, match="numeric or text fields"):
            gravar_metadados_ativo(database.cursor(), SimpleNamespace(**values))
    finally:
        database.close()