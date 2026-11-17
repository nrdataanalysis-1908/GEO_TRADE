from types import SimpleNamespace

import pytest

from src.ingestion.trade2_geo_trade_v2 import gravar_metadados_ativo, preparar_banco


def _metadata(**overrides):
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
    values.update(overrides)
    return SimpleNamespace(**values)


@pytest.mark.parametrize(
    "overrides",
    [
        {"volume_step": 0},
        {"volume_step": 2.0},
        {"volume_max": 0},
        {"volume_min": 1.1, "volume_max": 1.0},
    ],
)
def test_asset_metadata_rejects_incoherent_volume_constraints(tmp_path, overrides):
    database = preparar_banco(tmp_path / "volume-constraints.db")
    try:
        with pytest.raises(ValueError, match="volume_"):
            gravar_metadados_ativo(database.cursor(), _metadata(**overrides))
    finally:
        database.close()


def test_asset_metadata_accepts_consistent_volume_constraints(tmp_path):
    database = preparar_banco(tmp_path / "valid-volume-constraints.db")
    try:
        gravar_metadados_ativo(database.cursor(), _metadata())
        database.commit()
        row = database.execute(
            "SELECT volume_min, volume_max, volume_step FROM ativos WHERE symbol = ?",
            ("EURUSD",),
        ).fetchone()
        assert tuple(row) == (0.01, 1.0, 0.01)
    finally:
        database.close()