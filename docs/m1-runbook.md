# M1 Ingestion Runbook

## Objective

Operate and validate the MetaTrader 5 M1-to-SQLite ingestion with a repeatable procedure. This runbook describes the current script behavior; it is not a substitute for a live terminal integration test.

Entry point: `src/ingestion/trade2_geo_trade_v2.py`.

## Preconditions

- Windows environment with Python 3.10+.
- MetaTrader 5 desktop terminal installed.
- Terminal authenticated and able to access the requested market history.
- Python dependencies installed from `requirements.txt` (the M1 script imports `MetaTrader5` and `colorama`).
- A writable destination directory for the SQLite database.
- Correct instrument names as exposed by the connected MT5 terminal.

Do not place broker credentials, account identifiers or private terminal data in the repository.

## Execution

Create and activate the virtual environment:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Run the default extraction (previous Brasília calendar day):

```powershell
python .\src\ingestion\trade2_geo_trade_v2.py
```

Run a specific date and selected instruments:

```powershell
python .\src\ingestion\trade2_geo_trade_v2.py --date 2026-11-02 --symbols EURUSD GBPUSD
```

Choose a database path and suppress the optional DB Browser launch:

```powershell
python .\src\ingestion\trade2_geo_trade_v2.py --date 2026-11-02 --symbols EURUSD --db-path .\data\geo_trade.db --no-open-db
```

The script defaults to a database under the user's Downloads directory. Use `--db-path` when a reproducible project-local or dedicated data location is required. Generated databases should remain outside version control unless they contain intentionally curated public sample data.

## Expected execution sequence

1. Parse CLI arguments and resolve the Brasília calendar-day boundaries.
2. Convert the local interval to UTC.
3. Initialize the MT5 terminal using the configured executable path.
4. Verify that the terminal exposes an authenticated account; abort before creating the database when it does not.
5. Prepare the SQLite schema and indexes.
6. Resolve the requested symbols or enumerate symbols available in MT5.
7. Retrieve M1 history, filter records to the half-open UTC interval, validate candles and persist the accepted records.
8. Upsert instrument metadata.
9. Print execution totals and database validation information.
10. Close database and MT5 resources in the cleanup path.

## Post-run checks

Open the SQLite database with DB Browser for SQLite or run:

```sql
PRAGMA integrity_check;

SELECT
    symbol,
    timeframe,
    COUNT(*) AS candles,
    MIN(timestamp_utc) AS first_utc,
    MAX(timestamp_utc) AS last_utc
FROM candles
GROUP BY symbol, timeframe
ORDER BY symbol, timeframe;

SELECT symbol, timeframe, timestamp_utc, COUNT(*) AS occurrences
FROM candles
GROUP BY symbol, timeframe, timestamp_utc
HAVING COUNT(*) > 1;
```

Acceptance criteria:

- `PRAGMA integrity_check` returns `ok`.
- The duplicate-key query returns no rows.
- The selected symbols appear when the terminal returned history for them.
- Candle timestamps fall within the requested UTC interval.
- The script's inserted-row count is consistent with the database delta, allowing for rows already present from previous runs.

A run with zero new inserts is not automatically a failure: the interval may already have been imported. Inspect the number of records found and the existing database contents.

## Troubleshooting

| Symptom | Checks |
|---|---|
| MT5 initialization fails | Confirm terminal path, installation, terminal availability and authentication. Inspect `mt5.last_error()`. |
| Instrument not found | Copy the exact symbol from MT5 Market Watch; brokers may use suffixes or prefixes. |
| No candles returned | Confirm the instrument is enabled, history is available for the date and the terminal can access that timeframe. |
| SQLite cannot be written | Check destination directory permissions and whether another process is holding the database. |
| DB Browser does not open | The database may still have been saved; open the configured `.db` path manually. |
| Re-run inserts zero rows | Check whether the same natural keys already exist; inserts are intentionally idempotent. |

## Operational cautions

- The script uses UTC−03:00 for Brasília date interpretation. Revisit this assumption if the timezone policy changes.
- M1 candle timestamps represent bar times, not necessarily the time at which the extraction ran.
- The current idempotent insert does not overwrite previously stored candles if a broker revises historical data.
- A successful local run does not establish continuous availability, completeness across every broker, or trading performance.
- The M1 path depends on a locally authenticated MT5 terminal; automated CI cannot validate the live data connection without a controlled integration environment.

## Current limitations and next engineering steps

Not yet represented as implemented capabilities:

- Persistent run/audit table and extraction manifest.
- Structured logs and alerting.
- Retry policy and resumable checkpoints.
- Broker-correction reconciliation.
- Schema migration framework and retention policy.
- Automated integration tests against a controlled MT5 terminal.

These items should be implemented and tested before treating the ingestion as a production service.

## Additional quality gates

- An explicit `--date` value must be a real calendar date in `YYYY-MM-DD` format. Only an omitted date selects the previous Brasília calendar day; empty or falsey explicit values are invalid.
- Persistence requires a non-empty trimmed symbol and timezone-aware UTC interval boundaries with the end strictly later than the start.
- Identical duplicate candles for the same timestamp are collapsed. If bars at the same timestamp disagree on OHLCV/spread values, the entire timestamp group is rejected rather than allowing SQLite's `INSERT OR IGNORE` to select an arbitrary record.
- Invalid candles and duplicate rows contribute to the rejected-record count. The found/inserted totals represent unique accepted timestamps.
- The process returns a non-zero exit code when any symbol-level ingestion error occurs. A run with no history for a symbol remains a no-data condition, not automatically a transport failure.
- The H1 validator isolates numeric values that exceed float conversion limits, rejecting the affected rows instead of aborting the full batch. Feature engineering also validates its required columns and non-empty symbol/timeframe inputs before calculating indicators.

The unit suite covers these deterministic behaviors. It does not replace the live Windows/MT5 integration check described above.


## Transaction and data-conflict semantics

Each symbol is committed independently. If the operator interrupts extraction while a symbol is still being processed, the in-flight transaction is rolled back; previously committed symbols remain intact. This avoids publishing a partial symbol batch after an interrupt.

MT5 symbol lookup, symbol selection and history-query failures count as execution errors and produce a non-zero process exit status. An empty history response is treated separately as a symbol with no data.

When a timestamp already exists in SQLite, an identical candle is treated as an idempotent replay. A different OHLCV payload for the same natural key is not allowed to overwrite the stored candle; it is counted and reported as a persisted-data conflict. Review such conflicts before any controlled backfill or database correction.
