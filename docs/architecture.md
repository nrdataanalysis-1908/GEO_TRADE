# GEO_TRADE — Platform Architecture

## Design objective

Build a modular, testable market-data and quantitative-research platform. Keep source adapters, data-quality rules, storage, research workloads and user-facing services independently evolvable.

## Architecture diagram

![GEO_TRADE architecture](assets/geo-trade-architecture.svg)

Solid boxes in the diagram represent the current repository baseline. Dashed boxes are proposed roadmap components. The diagram is a target architecture, not a claim that all services are already deployed.

## Layer responsibilities

### 1. Market data sources

- Current: MetaTrader 5 desktop terminal through the Python integration.
- Future adapters: broker APIs, exchange feeds and optional alternative data.
- Normalize all timestamps to UTC at ingestion; preserve source timezone metadata where available.

### 2. Ingestion and data quality

- Extraction: symbol selection, timeframe selection, historical range and retry policy.
- Validation: OHLC consistency, null checks, duplicate detection, timestamp ordering and gap reporting.
- Feature engineering: candle anatomy, returns and technical indicators.
- Contracts: canonical instrument, timeframe, timestamp and OHLCV schema.
- Operational requirements: structured logs, run IDs, checkpointing and idempotent writes.

### 3. Storage and consumption

- Current: versioned CSV exports for reproducibility.
- Target: PostgreSQL with TimescaleDB where time-series query patterns justify it.
- Supabase may be used as a managed PostgreSQL and application integration layer; it is not a separate analytical database engine.
- Separate raw/source snapshots from validated and feature-enriched datasets. Preserve lineage and ingestion metadata.

### 4. Quantitative research and operations

- Backtesting: vectorized research for parameter exploration and/or event-driven simulation for order lifecycle realism.
- ML research: temporal splits, walk-forward validation, leakage controls and experiment tracking.
- API/dashboard: introduce only when there is a concrete consumer or workflow requirement.
- Observability: ingestion freshness, row counts, rejected records, missing intervals, latency and run status.

## Current implementation boundary

The current Python module performs a batch MT5 H1 collection, OHLC validation, descriptive feature calculation, UTC-day filtering, deduplication and CSV export. It is not yet a persistent data platform, backtesting engine, prediction service or execution system.

## Recommended implementation sequence

1. Validate the collector on the user's Windows + MT5 environment and add integration fixtures.
2. Add structured logging, run metadata, retry boundaries and quality reports.
3. Define canonical schemas and PostgreSQL migrations; then add idempotent persistence.
4. Add a research dataset interface and backtesting evaluation with transaction costs.
5. Add API, dashboard and ML workflows only after their data contracts are stable.

## Non-functional requirements

- Reproducibility: record parameters, symbol, timeframe, UTC range and software version per run.
- Reliability: bounded retries, explicit failure states, safe shutdown and resumable batches.
- Data integrity: idempotent keys, schema validation and quality metrics.
- Research validity: no look-ahead bias, no random train/test split for time series, and include spread, fees and slippage.
- Security: keep credentials and private market/account data out of Git.
