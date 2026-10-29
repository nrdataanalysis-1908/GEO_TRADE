from __future__ import annotations

import argparse
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

import MetaTrader5 as mt5
import numpy as np
import pandas as pd
from colorama import Fore, init

init(autoreset=True)
BLUE, CYAN, YELLOW, RED = Fore.LIGHTBLUE_EX, Fore.LIGHTCYAN_EX, Fore.LIGHTYELLOW_EX, Fore.LIGHTRED_EX
TIMEFRAME = mt5.TIMEFRAME_H1
TIMEFRAME_NAME = "H1"
WARMUP_HOURS = 60
ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TERMINAL = r"C:\Program Files\MetaTrader 5\terminal64.exe"


def parse_args():
    parser = argparse.ArgumentParser(description="GEO_TRADE | MT5 H1 market ingestion")
    parser.add_argument("--date", default=datetime.now(timezone.utc).date().isoformat(),
                        help="UTC date YYYY-MM-DD; defaults to current UTC date")
    parser.add_argument("--symbols", nargs="+", help="Optional MT5 symbols; default: all symbols")
    parser.add_argument("--terminal-path", default=DEFAULT_TERMINAL)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "data" / "exports")
    return parser.parse_args()


def utc_bounds(day_text):
    selected = date.fromisoformat(day_text)
    start = datetime.combine(selected, time.min, tzinfo=timezone.utc)
    return start, start + timedelta(days=1)


def add_features(rates, symbol, timeframe=TIMEFRAME_NAME):
    df = rates.copy()
    df["timestamp_utc"] = pd.to_datetime(df["time"], unit="s", utc=True)
    df["timestamp_brasilia"] = df["timestamp_utc"].dt.tz_convert("America/Sao_Paulo")
    df["symbol"], df["timeframe"] = symbol, timeframe
    df["candle_id"] = (df["symbol"] + "_" + df["timeframe"] + "_" +
                       df["timestamp_utc"].dt.strftime("%Y%m%d%H%M%S"))
    df["range"] = df["high"] - df["low"]
    df["body"] = df["close"] - df["open"]
    df["body_abs"] = df["body"].abs()
    df["upper_wick"] = df["high"] - df[["open", "close"]].max(axis=1)
    df["lower_wick"] = df[["open", "close"]].min(axis=1) - df["low"]
    df["candle_direction"] = np.select(
        [df["close"] > df["open"], df["close"] < df["open"]],
        ["BUY", "SELL"], default="DOJI")
    df["return"] = df["close"].pct_change()
    df["return_pct"] = df["return"] * 100
    for window in (5, 10):
        df[f"sma_{window}"] = df["close"].rolling(window).mean()
        df[f"ema_{window}"] = df["close"].ewm(span=window, adjust=False).mean()
    delta = df["close"].diff()
    gain, loss = delta.clip(lower=0), -delta.clip(upper=0)
    avg_gain, avg_loss = gain.rolling(14).mean(), loss.rolling(14).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    df["rsi_14"] = 100 - 100 / (1 + rs)
    df.loc[(avg_loss == 0) & (avg_gain > 0), "rsi_14"] = 100
    df.loc[(avg_loss == 0) & (avg_gain == 0), "rsi_14"] = 50
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - df["close"].shift()).abs(),
        (df["low"] - df["close"].shift()).abs()
    ], axis=1).max(axis=1)
    df["atr_14"] = tr.rolling(14).mean()
    ema12 = df["close"].ewm(span=12, adjust=False).mean()
    ema26 = df["close"].ewm(span=26, adjust=False).mean()
    df["macd"] = ema12 - ema26
    df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean()
    df["macd_histogram"] = df["macd"] - df["macd_signal"]
    middle = df["close"].rolling(20).mean()
    std = df["close"].rolling(20).std()
    df["bollinger_middle"] = middle
    df["bollinger_upper"], df["bollinger_lower"] = middle + 2 * std, middle - 2 * std
    df["volatility_10"] = df["return"].rolling(10).std()
    df["volatility_pct"] = df["volatility_10"] * 100
    for col, value in {
        "hour": df["timestamp_brasilia"].dt.hour,
        "day_of_week": df["timestamp_brasilia"].dt.dayofweek,
        "day_of_month": df["timestamp_brasilia"].dt.day,
        "month": df["timestamp_brasilia"].dt.month,
    }.items():
        df[col] = value
    return df.sort_values("timestamp_utc").reset_index(drop=True)


def validate_rates(rates):
    required = ["time", "open", "high", "low", "close"]
    clean = rates.dropna(subset=required).copy()
    valid = ((clean["high"] >= clean[["open", "close", "low"]].max(axis=1)) &
             (clean["low"] <= clean[["open", "close", "high"]].min(axis=1)) &
             (clean["high"] >= clean["low"]))
    clean = clean.loc[valid].copy()
    return clean, len(rates) - len(clean)


def collect_symbol(symbol, start, end):
    if not mt5.symbol_select(symbol, True):
        return None, 0, f"symbol_select: {mt5.last_error()}"
    rates = mt5.copy_rates_range(symbol, TIMEFRAME, start - timedelta(hours=WARMUP_HOURS), end)
    if rates is None:
        return None, 0, f"copy_rates_range: {mt5.last_error()}"
    if len(rates) == 0:
        return None, 0, None
    clean, rejected = validate_rates(pd.DataFrame(rates))
    if clean.empty:
        return None, rejected, "All bars failed OHLC validation"
    featured = add_features(clean, symbol)
    mask = (featured["timestamp_utc"] >= pd.Timestamp(start)) & (
        featured["timestamp_utc"] < pd.Timestamp(end))
    result = featured.loc[mask].copy()
    return (result if not result.empty else None), rejected, None


def main():
    args = parse_args()
    start, end = utc_bounds(args.date)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    output = args.output_dir / (
        f"GEO_TRADE_MARKET_H1_DAY_{args.date.replace('-', '')}_"
        f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
    connected = False
    frames, stats = [], {"with_data": 0, "without_data": 0, "errors": 0, "rejected": 0}
    try:
        if not mt5.initialize(path=args.terminal_path, timeout=120000):
            raise RuntimeError(f"MT5 initialize failed: {mt5.last_error()}")
        connected = True
        account = mt5.account_info()
        if account is None:
            raise RuntimeError(f"No authenticated MT5 account: {mt5.last_error()}")
        print(CYAN + f"Connected | account={account.login} | server={account.server}")
        if args.symbols:
            symbols = args.symbols
        else:
            found = mt5.symbols_get()
            if found is None:
                raise RuntimeError(f"symbols_get failed: {mt5.last_error()}")
            symbols = [item.name for item in found]
        for i, symbol in enumerate(symbols, 1):
            try:
                frame, rejected, error = collect_symbol(symbol, start, end)
                stats["rejected"] += rejected
                if error:
                    stats["errors"] += 1
                    print(RED + f"✗ [{i}/{len(symbols)}] {symbol}: {error}")
                elif frame is None:
                    stats["without_data"] += 1
                    print(YELLOW + f"— [{i}/{len(symbols)}] {symbol}: no data")
                else:
                    frames.append(frame)
                    stats["with_data"] += 1
                    print(CYAN + f"✓ [{i}/{len(symbols)}] {symbol}: {len(frame)} candles")
            except Exception as exc:
                stats["errors"] += 1
                print(RED + f"✗ {symbol}: {exc}")
        if not frames:
            print(RED + "No data collected; CSV not created.")
            return 1
        market = pd.concat(frames, ignore_index=True)
        market = market.drop_duplicates(["symbol", "timeframe", "timestamp_utc"])
        market = market.sort_values(["timestamp_utc", "symbol"]).reset_index(drop=True)
        columns = [
            "candle_id", "timestamp_utc", "timestamp_brasilia", "symbol", "timeframe",
            "open", "high", "low", "close", "tick_volume", "spread", "real_volume",
            "range", "body", "body_abs", "upper_wick", "lower_wick", "candle_direction",
            "return", "return_pct", "sma_5", "sma_10", "ema_5", "ema_10", "rsi_14",
            "atr_14", "macd", "macd_signal", "macd_histogram", "bollinger_upper",
            "bollinger_middle", "bollinger_lower", "volatility_10", "volatility_pct",
            "hour", "day_of_week", "day_of_month", "month"]
        market[columns].to_csv(output, index=False, encoding="utf-8-sig")
        print(CYAN + f"Exported {len(market)} candles to {output}")
        print(CYAN + f"Symbols with data={stats['with_data']} | without={stats['without_data']} "
                     f"| errors={stats['errors']} | rejected rows={stats['rejected']}")
        return 0
    except Exception as exc:
        print(RED + f"FATAL: {exc}")
        return 1
    finally:
        if connected:
            mt5.shutdown()
            print(CYAN + "MT5 connection closed.")


if __name__ == "__main__":
    raise SystemExit(main())
