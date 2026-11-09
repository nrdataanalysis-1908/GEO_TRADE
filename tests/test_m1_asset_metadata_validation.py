from types import SimpleNamespace

import pytest

from src.ingestion.trade2_geo_trade_v2 import gravar_metadados_ativo, preparar_banco


@pytest.mark.parametrize(
    "field,value",
    [
        ("digits", True),
        ("digits", -1),
        ("digits", 1.5),
        ("point", float("nan")),
        ("trade_tick_value", float("inf")),
        ("volume_min", -1),
        ("volume_step", float("nan")),
        ("description", "bad\\x00text"),
    ],
)
def test_asset_metadata_rejects_invalid_fields_before_persistence(tmp_path, field, value):
    database = preparar_banco(tmp_path / "metadata-validation.db")
    try:
        info = SimpleNamespace(name="EURUSD", **{field: value})
        with pytest.raises(ValueError, match="asset metadata contains invalid"):
            gravar_metadados_ativo(database.cursor(), info)
        assert database.execute("SELECT COUNT(*) FROM ativos").fetchone()[0] == 0
    finally:
        database.close()


def test_asset_metadata_rejects_inconsistent_volume_bounds(tmp_path):
    database = preparar_banco(tmp_path / "volume-bounds.db")
    try:
        info = SimpleNamespace(name="EURUSD", volume_min=2.0, volume_max=1.0)
        with pytest.raises(ValueError, match="asset metadata contains invalid"):
            gravar_metadados_ativo(database.cursor(), info)
        assert database.execute("SELECT COUNT(*) FROM ativos").fetchone()[0] == 0
    finally:
        database.close()
