from types import SimpleNamespace

import pandas as pd

import src.ingestion.market_ingestion as h1


class FakeTerminal:
    def __init__(self):
        self.shutdown_called = False

    def initialize(self, **kwargs):
        return True

    def account_info(self):
        return SimpleNamespace(login=123, server="demo")

    def symbols_get(self):
        return [
            SimpleNamespace(name="EURUSD"),
            SimpleNamespace(name="GBPUSD"),
        ]

    def shutdown(self):
        self.shutdown_called = True


def test_h1_main_returns_nonzero_when_partial_export_has_symbol_errors(
    monkeypatch, tmp_path
):
    terminal = FakeTerminal()
    monkeypatch.setattr(
        h1,
        "parse_args",
        lambda: SimpleNamespace(
            date="2026-11-03",
            symbols=None,
            terminal_path="fake-terminal",
            output_dir=tmp_path,
        ),
    )
    monkeypatch.setattr(h1, "mt5", terminal)

    timestamp = pd.Timestamp("2026-11-03T00:00:00Z")
    columns = [
        "candle_id", "timestamp_utc", "timestamp_brasilia", "symbol", "timeframe",
        "open", "high", "low", "close", "tick_volume", "spread", "real_volume",
        "range", "body", "body_abs", "upper_wick", "lower_wick", "candle_direction",
        "return", "return_pct", "sma_5", "sma_10", "ema_5", "ema_10", "rsi_14",
        "atr_14", "macd", "macd_signal", "macd_histogram", "bollinger_upper",
        "bollinger_middle", "bollinger_lower", "volatility_10", "volatility_pct",
        "hour", "day_of_week", "day_of_month", "month",
    ]
    values = {column: [0] for column in columns}
    values.update(
        {
            "candle_id": ["EURUSD_H1_20261103000000"],
            "timestamp_utc": [timestamp],
            "timestamp_brasilia": [timestamp.tz_convert("America/Sao_Paulo")],
            "symbol": ["EURUSD"],
            "timeframe": ["H1"],
        }
    )
    valid_frame = pd.DataFrame(values)

    def collect_symbol(symbol, start, end):
        if symbol == "EURUSD":
            return valid_frame, 0, None
        return None, 0, "simulated provider failure"

    monkeypatch.setattr(h1, "collect_symbol", collect_symbol)

    result = h1.main()

    assert result == 1
    exports = list(tmp_path.glob("GEO_TRADE_MARKET_H1_DAY_20261103_*.csv"))
    assert len(exports) == 1
    exported = pd.read_csv(exports[0], encoding="utf-8-sig")
    assert exported["symbol"].tolist() == ["EURUSD"]
    assert terminal.shutdown_called
