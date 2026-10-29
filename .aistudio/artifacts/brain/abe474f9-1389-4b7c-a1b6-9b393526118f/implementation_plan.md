# Rising Star Trend Engine - Sprint 1: DataConnector & Shared Schemas

Production-ready data ingestion pipeline and typed domain schemas for the Rising Star Trend Engine micro-services architecture. This sprint builds the core foundation that fetches, validates, and normalizes financial fundamentals and historical technical data for momentum and breakout analysis.

## User Review & Critical Decisions

> [!IMPORTANT]
> The following architectural decisions were confirmed based on the initial planning review:
> - **Lookback Window**: Default 60 trading days of historical market data, configurable on the connector.
> - **Data Incompleteness**: Optional fields with `None` defaults for missing fundamentals (e.g. short interest or float) to prevent complete ingestion dropouts while maintaining strict type safety.
> - **Resilience**: 3 retries with exponential backoff and jitter for transient network or rate-limiting (`429`) errors, with graceful `None` fallback and warning logging.

---

## 1. Overview & Core Concept

- **What It Does**: The `DataConnector` serves as the initial ingestion boundary in the trend engine. It queries market data providers (such as Yahoo Finance via `yfinance` or modular HTTP adapters), normalizes raw time-series prices and corporate fundamentals, and emits strictly validated `MarketDataPayload` models.
- **Target Audience / Persona**: Algorithmic trading strategies, quantitative researchers, and downstream microservices (e.g. Trend Filters, Catalyst Analyzers, and Portfolio Allocators).
- **Key Value**: Guarantees zero data-type drift across microservices, resiliently absorbs third-party API throttling, and extracts vital breakout indicators (such as 20-day highs and 10-day volume averages).

---

## 2. Module Interface & Design

```
┌──────────────────────────────────────────────────────────────┐
│                    Rising Star Trend Engine                  │
│                                                              │
│   ┌──────────────────┐               ┌──────────────────┐   │
│   │  Downstream      │◄──────────────│  DataConnector   │   │
│   │  Trend Strategy  │  Typed Payload│  Module          │   │
│   └──────────────────┘               └────────┬─────────┘   │
│                                               │             │
│                                               ▼             │
│                                    ┌─────────────────────┐  │
│                                    │  yfinance / Market  │  │
│                                    │  Data API Provider  │  │
│                                    └─────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

### Core Interfaces:
- **`src/schemas.py`**:
  - `FinancialMetrics`: Pydantic v2 model holding fundamental financial data (`market_cap`, `public_float`, `net_income_q1`, `net_income_ttm`, `short_interest_pct`).
  - `TechnicalMetrics`: Pydantic v2 model holding computed/observed price-action data (`avg_volume_10d`, `highs_20d`, `close_prices`, `volumes`, `latest_close`, `latest_volume`).
  - `MarketDataPayload`: Aggregated root model combining ticker, timestamp, financial metrics, and technical metrics with model validators ensuring consistency.
- **`src/data_connector.py`**:
  - `DataConnector`: Core connector class with `fetch_ticker_data(ticker: str) -> Optional[MarketDataPayload]`.
  - Configurable `max_retries` (default 3), `backoff_factor` (default 1.5s), and `lookback_days` (default 60).
  - Explicit rate-limit and network error backoff with logging via Python's standard `logging` module.
- **`tests/test_data_connector.py`**:
  - Comprehensive unit tests mocking `yfinance.Ticker` methods (`history`, `info`, `quarterly_financials`).
  - Test suites verifying valid payload generation, missing ticker handling, rate limit retries, and calculation accuracy (e.g., 20-day high and 10-day volume).

---

## 3. Key Technical Decisions & Trade-Offs

- **Pydantic v2 Schema Design**:
  - *Chosen Approach*: Use `pydantic.BaseModel` with `ConfigDict(frozen=True)` or standard validation, explicit type annotations, and field documentation.
  - *Why*: Pydantic v2 provides blazing-fast C/Rust-backed validation, native JSON serialization, and immutable payloads preventing accidental mutation downstream.
  - *Alternatives Considered*: Python standard `dataclasses` (lack runtime validation, coercive parsing, and serialization flexibility).

- **Resilience & Retry Architecture**:
  - *Chosen Approach*: Clean internal decorator/loop implementing exponential backoff with retryable exceptions (e.g., HTTP 429, connection errors, timeout).
  - *Why*: Minimizes external dependencies while guaranteeing predictable backoff behavior without hiding unrecoverable programming errors.
  - *Alternatives Considered*: Third-party libraries like `tenacity` or `urllib3` retry handlers (adding external package overhead when standard library logic provides cleaner test isolation).

- **Data Normalization & Calculation**:
  - *Chosen Approach*: Safe calculation of `avg_volume_10d` and `highs_20d` directly from the validated slice of historical bars, returning `None` gracefully if historical bar count is insufficient for meaningful analysis.
  - *Why*: Prevents `ZeroDivisionError` or `IndexError` when newly listed IPO tickers have fewer than 10 or 20 days of trading history.

---

## 4. Technical Architecture & Data Strategy

### System & Pipeline Diagram

```
                 ┌────────────────────────────────┐
                 │       DataConnector.fetch      │
                 │          (ticker: str)         │
                 └───────────────┬────────────────┘
                                 │
                 ┌───────────────▼────────────────┐
                 │    Exponential Backoff Loop    │
                 │  (3 retries, backoff + jitter) │
                 └───────────────┬────────────────┘
                                 │
          ┌──────────────────────┴──────────────────────┐
          │                                             │
┌─────────▼──────────────┐                   ┌──────────▼───────────┐
│ Fetch OHLCV History    │                   │ Fetch Fundamentals   │
│ (close, volume, highs) │                   │ (cap, float, income) │
└─────────┬──────────────┘                   └──────────┬───────────┘
          │                                             │
          └──────────────────────┬──────────────────────┘
                                 │
                 ┌───────────────▼────────────────┐
                 │ Validate Raw Data via Pydantic │
                 │ - FinancialMetrics             │
                 │ - TechnicalMetrics             │
                 └───────────────┬────────────────┘
                                 │
                 ┌───────────────▼────────────────┐
                 │ Emit MarketDataPayload Object  │
                 └────────────────────────────────┘
```

### Schema Definitions Summary (`src/schemas.py`)
- `FinancialMetrics`:
  - `market_cap: Optional[float] = None`
  - `public_float: Optional[float] = None`
  - `net_income_q1: Optional[float] = None`
  - `net_income_ttm: Optional[float] = None`
  - `short_interest_pct: Optional[float] = None`
- `TechnicalMetrics`:
  - `avg_volume_10d: float`
  - `highs_20d: float`
  - `close_prices: List[float]`
  - `volumes: List[int]`
  - `latest_close: float`
  - `latest_volume: int`
- `MarketDataPayload`:
  - `ticker: str`
  - `as_of: datetime`
  - `financials: FinancialMetrics`
  - `technicals: TechnicalMetrics`

### Test Verification Matrix (`tests/test_data_connector.py`)
1. `test_successful_market_data_payload_creation`: Mocks valid OHLCV and fundamentals; verifies payload structure and accurate 10d volume / 20d high calculation.
2. `test_missing_ticker_returns_none`: Mocks empty DataFrame / invalid ticker; confirms warning log and `None` return.
3. `test_retry_logic_on_rate_limit_and_network_error`: Mocks initial rate limits followed by recovery; verifies backoff and eventual success.
4. `test_unrecoverable_error_exhausts_retries`: Mocks persistent 429/timeout errors; verifies graceful failure returning `None`.
5. `test_short_history_graceful_handling`: Tickers with fewer than 20 days of data are handled safely without crashing.
