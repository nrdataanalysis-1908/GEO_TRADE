from types import SimpleNamespace

import pytest

from src.ingestion.trade2_geo_trade_v2 import (
    gravar_metadados_ativo,
    preparar_banco,
)


@pytest.mark.parametrize("digits", [2**63, 2**64])
def test_asset_metadata_rejects_digits_outside_sqlite_integer_range(tmp_path, digits):
    database = preparar_banco(tmp_path / "digits-overflow.db")
    try:
        info = SimpleNamespace(name="EURUSD", digits=digits)

        with pytest.raises(ValueError, match="asset metadata contains invalid"):
            gravar_metadados_ativo(database.cursor(), info)

        assert database.execute("SELECT COUNT(*) FROM ativos").fetchone()[0] == 0
    finally:
        database.close()
