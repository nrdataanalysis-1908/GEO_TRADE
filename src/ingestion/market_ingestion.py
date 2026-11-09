from __future__ import annotations

import argparse
import os
import tempfile
import re
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

try:
    import MetaTrader5 as mt5
except ImportError:  # MT5 is a Windows terminal integration, not a unit-test dependency.
    mt5 = None

import numpy as np
import pandas as pd
from colorama import Fore, init

init(autoreset=True)
BLUE, CYAN, YELLOW, RED = Fore.LIGHTBLUE_EX, Fore.LIGHTCYAN_EX, Fore.LIGHTYELLOW_EX, Fore.LIGHTRED_EX
TIMEFRAME = getattr(mt5, "TIMEFRAME_H1", None)
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
    if not isinstance(day_text, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day_text):
        raise ValueError("date must use YYYY-MM-DD")
    selected = date.fromisoformat(day_text)
    start = datetime.combine(selected, time.min, tzinfo=timezone.utc)
    try:
        end = start + timedelta(days=1)
    except OverflowError as exc:
        raise ValueError("date must allow an exclusive next-day boundary") from exc
    return start, end


def validate_symbols(symbols):
    """Validate an explicit H1 symbol list without changing its order."""
    if symbols is None:
        return None
    if not isinstance(symbols, (list, tuple)) or not symbols:
        raise ValueError("symbols must be a non-empty list when provided")
    normalized = []
    seen = set()
    for symbol in symbols:
        if (
            not isinstance(symbol, str)
            or not symbol.strip()
            or symbol != symbol.strip()
            or any(ord(character) < 32 or ord(character) == 127 for character in symbol)
        ):
            raise ValueError(
                "each symbol must be a non-empty trimmed string without control characters"
            )
        if symbol in seen:
            raise ValueError(f"duplicate symbol argument: {symbol}")
        seen.add(symbol)
        normalized.append(symbol)
    return normalized


def _parse_integral_timestamp(value):
    """Return exact Unix seconds only when the value is integral and pandas-representable."""
    if isinstance(value, (bool, np.bool_)):
        return None
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    if not number.is_finite() or number != number.to_integral_value():
        return None
    try:
        timestamp = int(number)
        converted = pd.to_datetime(timestamp, unit="s", utc=True, errors="coerce")
    except (OverflowError, TypeError, ValueError):
        return None
    return None if pd.isna(converted) else timestamp


def add_features(rates, symbol, timeframe=TIMEFRAME_NAME):
    if not isinstance(rates, pd.DataFrame):
        raise TypeError("rates must be a pandas DataFrame")
    if not isinstance(symbol, str) or not symbol.strip() or symbol != symbol.strip():
        raise ValueError("symbol must be a non-empty trimmed string")
    if not isinstance(timeframe, str) or not timeframe.strip() or timeframe != timeframe.strip():
        raise ValueError("timeframe must be a non-empty trimmed string")
    required = ("time", "open", "high", "low", "close")
    missing = [column for column in required if column not in rates.columns]
    if missing:
        raise ValueError(f"Missing required feature columns: {', '.join(missing)}")
    duplicates = [column for column in required if list(rates.columns).count(column) > 1]
    if duplicates:
        raise ValueError(f"Duplicate feature columns: {', '.join(duplicates)}")
    if rates.empty:
        raise ValueError("rates must contain at least one market bar")

    df = rates.copy().reset_index(drop=True)
    boolean_rows = df[list(required)].apply(
        lambda column: column.map(
            lambda value: isinstance(value, (bool, np.bool_))
        )
    ).any(axis=1)
    parsed_times = [_parse_integral_timestamp(value) for value in df["time"].tolist()]
    if any(value is None for value in parsed_times):
        raise ValueError("time values must be exact integral Unix seconds within pandas range")
    df["time"] = pd.Series(parsed_times, index=df.index, dtype="int64")
    try:
        for column in required[1:]:
            df[column] = pd.to_numeric(df[column], errors="coerce")
        numeric_values = df[list(required)].to_numpy(dtype=float)
    except (OverflowError, TypeError, ValueError) as exc:
        raise ValueError("feature columns must contain finite numeric values") from exc
    if boolean_rows.any() or not np.isfinite(numeric_values).all():
        raise ValueError("feature columns must contain finite numeric values")

    timestamps = pd.to_datetime(df["time"], unit="s", utc=True, errors="coerce")
    if timestamps.isna().any():
        raise ValueError("time values must be representable as UTC timestamps")
    if df["time"].duplicated().any():
        raise ValueError("time values must be unique per symbol and timeframe")

    prices = df[["open", "high", "low", "close"]].to_numpy(dtype=float)
    opening, highest, lowest, closing = prices.T
    if (
        (prices <= 0).any()
        or (highest < np.maximum(opening, closing)).any()
        or (lowest > np.minimum(opening, closing)).any()
        or (highest < lowest).any()
    ):
        raise ValueError("OHLC values must be positive and internally consistent")

    # Rolling indicators must be calculated in chronological order, not merely sorted afterward.
    df = df.sort_values("time", kind="stable").reset_index(drop=True)
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
        "day_of_week": df["timestamp_brasilia"].dt.day_of_week,
        "day_of_month": df["timestamp_brasilia"].dt.day,
        "month": df["timestamp_brasilia"].dt.month,
    }.items():
        df[col] = value
    return df.sort_values("timestamp_utc").reset_index(drop=True)


def _safe_numeric_value(value):
    try:
        return float(value)
    except (TypeError, ValueError, OverflowError):
        return np.nan


def validate_rates(rates):
    if not isinstance(rates, pd.DataFrame):
        raise TypeError("rates must be a pandas DataFrame")
    required = [
        "time", "open", "high", "low", "close",
        "tick_volume", "spread", "real_volume",
    ]
    missing = sorted(set(required) - set(rates.columns))
    if missing:
        raise ValueError(f"Missing required market columns: {', '.join(missing)}")
    duplicates = sorted(set(rates.columns[rates.columns.duplicated()].tolist()))
    if duplicates:
        raise ValueError(f"Duplicate market columns: {', '.join(duplicates)}")

    clean = rates.copy().reset_index(drop=True)
    boolean_rows = clean[required].apply(
        lambda column: column.map(lambda value: isinstance(value, (bool, np.bool_)))
    ).any(axis=1)
    parsed_times = [_parse_integral_timestamp(value) for value in clean["time"].tolist()]
    clean["time"] = pd.Series(parsed_times, index=clean.index, dtype="object")
    for column in ("open", "high", "low", "close", "tick_volume", "spread", "real_volume"):
        try:
            clean[column] = pd.to_numeric(clean[column], errors="coerce")
        except (OverflowError, TypeError, ValueError):
            # One out-of-range Python integer can make pandas abort the entire
            # column conversion. Fall back to row-wise coercion so that only
            # malformed records are rejected instead of the complete batch.
            clean[column] = clean[column].map(_safe_numeric_value)
    clean = clean.dropna(subset=required).copy()
    if clean.empty:
        return clean, len(rates)
    clean["time"] = clean["time"].astype("int64")

    prices = clean[["open", "high", "low", "close"]].to_numpy(dtype=float)
    valid = ~boolean_rows.loc[clean.index].to_numpy()
    valid &= np.isfinite(prices).all(axis=1)
    valid &= (prices > 0).all(axis=1)
    representable = pd.to_datetime(clean["time"], unit="s", utc=True, errors="coerce")
    valid &= representable.notna().to_numpy()

    for column in ("tick_volume", "spread", "real_volume"):
        values = clean[column].to_numpy(dtype=float)
        valid &= np.isfinite(values) & (values >= 0) & (values == np.floor(values))

    valid &= (
        (clean["high"] >= clean[["open", "close", "low"]].max(axis=1)).to_numpy()
        & (clean["low"] <= clean[["open", "close", "high"]].min(axis=1)).to_numpy()
        & (clean["high"] >= clean["low"]).to_numpy()
    )
    clean = clean.loc[valid].copy().sort_values("time", kind="stable")

    # Identical duplicate bars collapse to one row. Conflicting bars for the
    # same timestamp are all rejected instead of selecting an arbitrary price.
    duplicate_rows = clean.loc[clean.duplicated("time", keep=False)]
    indexes_to_drop = []
    market_columns = [column for column in required if column != "time"]
    for _, group in duplicate_rows.groupby("time", sort=False):
        if len(group[market_columns].drop_duplicates()) == 1:
            indexes_to_drop.extend(group.index[1:])
        else:
            indexes_to_drop.extend(group.index)
    if indexes_to_drop:
        clean = clean.drop(index=indexes_to_drop)

    return clean.reset_index(drop=True), len(rates) - len(clean)


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



def _write_csv_atomically(frame, destination, columns):
    """Publish a complete CSV or leave the previous destination untouched."""
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    os.close(descriptor)
    try:
        frame[columns].to_csv(temporary_name, index=False, encoding="utf-8-sig")
        with open(temporary_name, "rb") as stream:
            os.fsync(stream.fileno())
        os.replace(temporary_name, destination)
    except Exception:
        Path(temporary_name).unlink(missing_ok=True)
        raise


def main():
    args = parse_args()
    try:
        args.symbols = validate_symbols(getattr(args, "symbols", None))
    except ValueError as exc:
        print(RED + f"Invalid symbols: {exc}")
        return 2
    print(CYAN + "GEO_TRADE | Desenvolvido por Nadison Roberto | NR TECH | © 2026")
    if mt5 is None:
        print(RED + "MetaTrader5 package is required for live H1 ingestion.")
        return 2
    try:
        start, end = utc_bounds(args.date)
    except ValueError as exc:
        print(RED + f"Invalid date: {exc}")
        return 2
    try:
        args.output_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        print(RED + f"Cannot create output directory {args.output_dir}: {exc}")
        return 1
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
        _write_csv_atomically(market, output, columns)
        print(CYAN + f"Exported {len(market)} candles to {output}")
        print(CYAN + f"Symbols with data={stats['with_data']} | without={stats['without_data']} "
                     f"| errors={stats['errors']} | rejected rows={stats['rejected']}")
        return 1 if stats["errors"] else 0
    except Exception as exc:
        print(RED + f"FATAL: {exc}")
        return 1
    finally:
        if connected:
            mt5.shutdown()
            print(CYAN + "MT5 connection closed.")


if __name__ == "__main__":
    raise SystemExit(main())
