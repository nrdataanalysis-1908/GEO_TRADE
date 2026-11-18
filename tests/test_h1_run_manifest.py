import hashlib
import json
from argparse import Namespace
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from src.ingestion import market_ingestion as h1
from src.ingestion.market_ingestion import add_features


class _ManifestTerminal:
    def __init__(self, symbols):
        self._symbols = symbols

    def initialize(self, **kwargs):
        return True

    def account_info(self):
        return SimpleNamespace()

    def symbols_get(self):
        return [SimpleNamespace(name=name) for name in self._symbols]

    def shutdown(self):
        return None


def _rates():
    return pd.DataFrame({
        "time": np.arange(1_700_000_000, 1_700_000_000 + 20 * 3600, 3600),
        "open": np.linspace(1.0, 1.02, 20),
        "high": np.linspace(1.01, 1.03, 20),
        "low": np.linspace(0.99, 1.01, 20),
        "close": np.linspace(1.005, 1.025, 20),
        "tick_volume": np.full(20, 100),
        "spread": np.full(20, 2),
        "real_volume": np.zeros(20),
    })


@pytest.mark.parametrize(
    ("symbols", "outcomes", "expected_status", "expected_exit"),
    [
        (["GOOD"], {"GOOD": (0, None)}, "complete", 0),
        (["GOOD", "BAD"], {"GOOD": (0, None), "BAD": (0, "simulated failure")}, "partial", 1),
        (["GOOD"], {"GOOD": (2, None)}, "degraded", 0),
    ],
)
def test_h1_main_publishes_auditable_run_manifest(
    monkeypatch, tmp_path, symbols, outcomes, expected_status, expected_exit
):
    terminal = _ManifestTerminal(symbols)
    featured = {
        name: add_features(_rates(), name)
        for name in symbols
        if name == "GOOD"
    }

    def collect(symbol, start, end):
        rejected, error = outcomes[symbol]
        if error:
            return None, rejected, error
        return featured[symbol], rejected, None

    monkeypatch.setattr(h1, "mt5", terminal)
    monkeypatch.setattr(
        h1,
        "parse_args",
        lambda: Namespace(
            date="2026-11-03",
            symbols=None,
            terminal_path="unused",
            output_dir=tmp_path,
        ),
    )
    monkeypatch.setattr(h1, "collect_symbol", collect)

    assert h1.main() == expected_exit

    csv_files = list(tmp_path.glob("GEO_TRADE_MARKET_H1_DAY_20261103_*.csv"))
    assert len(csv_files) == 1
    manifest_path = csv_files[0].with_suffix(".manifest.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert manifest["status"] == expected_status
    assert manifest["csv_file"] == csv_files[0].name
    assert manifest["csv_sha256"] == hashlib.sha256(csv_files[0].read_bytes()).hexdigest()
    assert manifest["rows_exported"] == 20
    assert manifest["symbols_requested"] == len(symbols)
    assert manifest["symbols_with_data"] == 1
    assert manifest["symbols_with_errors"] == int(expected_status == "partial")
    assert manifest["rejected_rows"] == outcomes["GOOD"][0]
    assert manifest["failed_symbols"] == (["BAD"] if expected_status == "partial" else [])


def test_atomic_manifest_preserves_previous_file_when_payload_is_not_strict_json(tmp_path):
    destination = tmp_path / "run.manifest.json"
    destination.write_text('{"previous": true}\n', encoding="utf-8")

    with pytest.raises(ValueError):
        h1._write_json_atomically({"not_finite": float("nan")}, destination)

    assert destination.read_text(encoding="utf-8") == '{"previous": true}\n'
    assert not list(tmp_path.glob(".run.manifest.json.*.tmp"))
