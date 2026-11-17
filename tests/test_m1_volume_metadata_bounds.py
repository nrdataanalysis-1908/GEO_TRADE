from types import SimpleNamespace

import pytest

from src.ingestion.trade2_geo_trade_v2 import gravar_metadados_ativo, preparar_banco


@pytest.mark.parametrize(
    "volume_min,volume_max,volume_step",
    [
        (0.1, 0.0, 0.01),
        (0.1, 1.0, 0.0),
        (0.1, 1.0, 1.1),
        (1.1, 1.0, 0.1),
    ],
)
def test_asset_metadata_rejects_inconsistent_volume_constraints(
    tmp_path, volume_min, volume_max, volume_step
):
    database = preparar_banco(tmp_path / "invalid-volume-metadata.db")
    try:
        info = SimpleNamespace(
            name="EURUSD",
            volume_min=volume_min,
            volume_max=volume_max,
            volume_step=volume_step,
        )
        with pytest.raises(ValueError, match="asset metadata contains invalid"):
            gravar_metadados_ativo(database.cursor(), info)

        assert database.execute("SELECT COUNT(*) FROM ativos").fetchone()[0] == 0
    finally:
        database.close()


def test_asset_metadata_persists_coherent_volume_constraints(tmp_path):
    database = preparar_banco(tmp_path / "valid-volume-metadata.db")
    try:
        info = SimpleNamespace(
            name="EURUSD",
            volume_min=0.01,
            volume_max=100.0,
            volume_step=0.01,
        )
        gravar_metadados_ativo(database.cursor(), info)

        assert database.execute(
            "SELECT volume_min, volume_max, volume_step FROM ativos WHERE symbol = ?",
            ("EURUSD",),
        ).fetchone() == (0.01, 100.0, 0.01)
    finally:
        database.close()
