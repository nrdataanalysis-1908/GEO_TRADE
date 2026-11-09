import pandas as pd

import src.ingestion.market_ingestion as h1


def test_atomic_csv_writer_opens_temp_file_with_write_access_for_fsync(monkeypatch, tmp_path):
    real_open = open
    modes = []

    def tracked_open(file, mode="r", *args, **kwargs):
        if str(file).startswith(str(tmp_path)) and str(file).endswith(".tmp"):
            modes.append(mode)
        return real_open(file, mode, *args, **kwargs)

    monkeypatch.setattr(h1, "open", tracked_open, raising=False)
    destination = tmp_path / "market.csv"
    h1._write_csv_atomically(pd.DataFrame({"symbol": ["EURUSD"]}), destination, ["symbol"])

    assert "rb+" in modes
    assert destination.read_text(encoding="utf-8-sig").splitlines() == ["symbol", "EURUSD"]
