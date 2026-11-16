from datetime import datetime

from src.ingestion.market_ingestion import _build_output_path


def test_h1_output_paths_do_not_collide_for_runs_in_the_same_second(tmp_path):
    first = _build_output_path(
        tmp_path,
        "2026-11-15",
        datetime(2026, 11, 15, 8, 0, 0, 123456),
    )
    second = _build_output_path(
        tmp_path,
        "2026-11-15",
        datetime(2026, 11, 15, 8, 0, 0, 654321),
    )

    assert first != second
    assert first.name.endswith("_080000_123456.csv")
    assert second.name.endswith("_080000_654321.csv")
