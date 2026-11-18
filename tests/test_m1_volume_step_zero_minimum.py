from types import SimpleNamespace

import pytest

from src.ingestion.trade2_geo_trade_v2 import gravar_metadados_ativo, preparar_banco


def _asset(**overrides):
    values = {
        "name": "EURUSD",
        "volume_min": 0,
        "volume_max": 1.0,
        "volume_step": 0,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_positive_volume_max_requires_a_positive_step_even_when_minimum_is_zero(tmp_path):
    database = preparar_banco(tmp_path / "zero-minimum-step.db")
    try:
        with pytest.raises(ValueError, match="asset metadata contains invalid"):
            gravar_metadados_ativo(database.cursor(), _asset())
        assert database.execute("SELECT COUNT(*) FROM ativos").fetchone()[0] == 0
    finally:
        database.close()


def test_zero_volume_minimum_accepts_a_positive_step_when_maximum_is_positive(tmp_path):
    database = preparar_banco(tmp_path / "zero-minimum-valid-step.db")
    try:
        gravar_metadados_ativo(
            database.cursor(), _asset(volume_step=0.01)
        )
        database.commit()
        row = database.execute(
            "SELECT volume_min, volume_max, volume_step FROM ativos WHERE symbol = ?",
            ("EURUSD",),
        ).fetchone()
        assert tuple(row) == (0.0, 1.0, 0.01)
    finally:
        database.close()
