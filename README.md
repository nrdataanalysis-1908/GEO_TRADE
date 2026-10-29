# GEO_TRADE — Financial Market Data Engineering

Public portfolio project for market-data ingestion, feature engineering, data-quality validation and reproducible CSV exports using Python and MetaTrader 5.

> Current scope: daily H1 candle extraction from a connected MetaTrader 5 terminal. PostgreSQL/Supabase, API, dashboard and quantitative research are planned stages, not claimed as implemented.

## Architecture

```text
MetaTrader 5 Terminal
        |
        v
Python ingestion (src/ingestion/market_ingestion.py)
        |
        v
Pandas transformations + technical features
        |
        v
CSV export (data/exports/ — ignored by Git)
```

## Requirements

- Windows with MetaTrader 5 desktop terminal installed.
- A valid, authenticated account in the terminal.
- Python 3.10+ and access to the requested symbol history.

## Setup (PowerShell)

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

If activation is blocked, use ` .\.venv\Scripts\python.exe ` to run Python directly.

## Run

```powershell
python -m src.ingestion.market_ingestion
python -m src.ingestion.market_ingestion --date 2026-08-21
python -m src.ingestion.market_ingestion --date 2026-08-21 --symbols EURUSD GBPUSD USDJPY
```

The requested date is interpreted as a UTC calendar date. The collector fetches preceding H1 candles as warm-up history before calculating rolling indicators, then exports only candles in the requested UTC day. The last H1 candle can still be forming.

`candle_direction` describes candle movement; it is not a trading signal. Indicators are descriptive features, not evidence of predictive power or profitability.

## Tests

```powershell
python -m pytest
```

## Roadmap

1. Stabilize and test MT5 ingestion.
2. Add PostgreSQL/Supabase persistence and migrations.
3. Add a Java/Spring Boot API if justified by integration requirements.
4. Add dashboard and ingestion observability.
5. Add reproducible backtesting and ML research with temporal validation and leakage controls.

## Security

Never commit passwords, API keys, `.env` files, terminal data folders, or raw account information. Public repository contents should contain source code and documentation only.
