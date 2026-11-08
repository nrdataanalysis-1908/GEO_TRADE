# M1 SQLite Data Contract

## Purpose

This document defines the persisted data contract for the M1 historical ingestion implemented in `src/ingestion/trade2_geo_trade_v2.py`.

The pipeline stores raw MetaTrader 5 one-minute bars and instrument metadata. It does not calculate indicators, generate trading signals, or execute orders.

## Entities

### `ativos`

One row per instrument symbol. The `symbol` column is unique.

| Column | Meaning |
|---|---|
| `id` | Local integer primary key |
| `symbol` | MT5 instrument name; unique business key |
| `description` | Instrument description supplied by MT5 |
| `path` | MT5 instrument group/path |
| `currency_base` | Base currency |
| `currency_profit` | Profit currency |
| `currency_margin` | Margin currency |
| `digits` | Display precision |
| `point` | Point size |
| `trade_tick_size` | Minimum tick size |
| `trade_tick_value` | Tick value |
| `volume_min`, `volume_max`, `volume_step` | Broker volume constraints |
| `created_at` | UTC timestamp of the initial metadata insertion |

Metadata is inserted once and subsequently refreshed with an `ON CONFLICT(symbol) DO UPDATE` operation. The upsert deliberately does not update `created_at`; it remains the original registration timestamp. The current schema does not expose a separate last-synchronized timestamp.

### `candles`

One row per instrument, timeframe and UTC candle timestamp.

| Column | Meaning |
|---|---|
| `id` | Local integer primary key |
| `timestamp_utc` | Candle opening timestamp in UTC, ISO 8601 |
| `timestamp_brasilia` | Same instant represented at UTC−03:00 |
| `symbol` | MT5 instrument name |
| `timeframe` | Timeframe identifier; currently `M1` |
| `open`, `high`, `low`, `close` | OHLC prices |
| `tick_volume` | MT5 tick volume |
| `spread` | MT5 spread field |
| `real_volume` | MT5 real volume field |

The natural uniqueness constraint is `(symbol, timeframe, timestamp_utc)`. The table also has indexes on `symbol`, `timestamp_utc` and `(symbol, timestamp_utc)`.

## Time semantics

- The requested `--date` is interpreted as a Brasília calendar date at UTC−03:00.
- The extraction window is the local day converted to UTC.
- The interval is half-open: `[start_utc, end_utc)`. A candle exactly at the next day's boundary is excluded.
- Timestamps are persisted as ISO 8601 strings with explicit offsets.
- Use `timestamp_utc` for cross-market joins and chronological comparisons. Use `timestamp_brasilia` for local operational inspection.

## Idempotency and update behavior

- Re-importing the same instrument/timeframe/timestamp does not create a duplicate candle because the insert uses `INSERT OR IGNORE`.
- Existing candle rows are not updated by a repeated import. This protects the original persisted observation, but it also means later broker corrections to historical bars are not automatically reconciled.
- Instrument metadata is refreshed through an upsert.
- The current schema does not define a foreign key from `candles.symbol` to `ativos.symbol`.

## Consumer validation checklist

Before using the data for research:

1. Confirm that `symbol`, `timeframe` and `timestamp_utc` are populated.
2. Check uniqueness at the declared natural key.
3. Check that `timestamp_brasilia` represents the same instant as `timestamp_utc`.
4. Verify that each candle belongs to the requested half-open UTC interval.
5. Inspect OHLC consistency: `high >= max(open, close)` and `low <= min(open, close)`.
6. Treat zero or missing volume values according to the instrument and broker's market-data conventions; do not assume all instruments provide real volume.
7. Record the extraction date and source terminal/account context in any downstream research manifest.

## Example SQL

Duplicate-key check (expected result: no rows):

```sql
SELECT symbol, timeframe, timestamp_utc, COUNT(*) AS row_count
FROM candles
GROUP BY symbol, timeframe, timestamp_utc
HAVING COUNT(*) > 1;
```

Coverage by instrument:

```sql
SELECT
    symbol,
    timeframe,
    COUNT(*) AS candle_count,
    MIN(timestamp_utc) AS first_utc,
    MAX(timestamp_utc) AS last_utc
FROM candles
GROUP BY symbol, timeframe
ORDER BY symbol, timeframe;
```

OHLC anomaly scan:

```sql
SELECT symbol, timestamp_utc, open, high, low, close
FROM candles
WHERE high < MAX(open, close)
   OR low > MIN(open, close);
```

## Scope

This contract documents the current M1 SQLite schema only. It does not imply that data lineage manifests, broker correction handling, schema migrations, retention policies or automated quality gates are already implemented.
