# Architecture

## Current implementation

The ingestion module is a batch ETL process:

1. Connect to an authenticated MetaTrader 5 terminal.
2. Resolve explicitly requested symbols or all terminal symbols.
3. Select each symbol in Market Watch.
4. Fetch H1 rates with a preceding warm-up window.
5. Calculate candle features and technical indicators chronologically.
6. Filter the transformed data to the requested UTC day.
7. Validate OHLC consistency and deduplicate by symbol, timeframe and timestamp.
8. Export one consolidated CSV and print a run summary.

## Planned evolution

```text
MT5 -> Python collector -> validation -> PostgreSQL/Supabase
                                      -> REST API
                                      -> analytics/dashboard
```

PostgreSQL/Supabase and the Java/Spring Boot service are future work, not current functionality.
