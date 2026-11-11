import builtins

import pandas as pd
import pytest

from src.ingestion.market_ingestion import _write_csv_atomically


def test_atomic_export_replaces_destination_with_utf8_bom(tmp_path):
    destination = tmp_path / "market.csv"
    destination.write_text("previous export", encoding="utf-8")
    frame = pd.DataFrame({"time": [1_700_000_000], "close": [1.1]})

    _write_csv_atomically(frame, destination, ["time", "close"])

    assert destination.read_bytes().startswith(b"\xef\xbb\xbf")
    assert destination.read_text(encoding="utf-8-sig") == "time,close\n1700000000,1.1\n"
    assert list(tmp_path.glob(".market.csv.*.tmp")) == []


def test_atomic_export_preserves_previous_file_when_serialization_fails(tmp_path):
    destination = tmp_path / "market.csv"
    destination.write_bytes(b"previous export")

    class BrokenFrame:
        def __getitem__(self, columns):
            return self

        def to_csv(self, *args, **kwargs):
            raise OSError("simulated serialization failure")

    with pytest.raises(OSError, match="simulated serialization failure"):
        _write_csv_atomically(BrokenFrame(), destination, ["time", "close"])

    assert destination.read_bytes() == b"previous export"
    assert list(tmp_path.glob(".market.csv.*.tmp")) == []


def test_atomic_export_opens_fsync_handle_with_write_access(tmp_path, monkeypatch):
    destination = tmp_path / "market.csv"
    frame = pd.DataFrame({"time": [1], "close": [1.1]})
    real_open = builtins.open
    fsync_modes = []

    def tracked_open(file, mode="r", *args, **kwargs):
        if str(file).endswith(".tmp") and mode == "rb+":
            fsync_modes.append(mode)
        return real_open(file, mode, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", tracked_open)

    _write_csv_atomically(frame, destination, ["time", "close"])

    assert fsync_modes == ["rb+"]
