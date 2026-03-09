# Architecture — QuantCore

## System Overview

QuantCore (`qxm`) is a quantitative trading engine that simulates order matching, risk computation, and portfolio analytics. It's structured as a modular Python package with clear separation of concerns.

```
┌──────────────────────────────────────────────────────────┐
│                     Clients                              │
│         (REST API / MCP Server / Dashboard)              │
└────────────────┬──────────────────┬──────────────────────┘
                 │                  │
         ┌───────▼──────┐   ┌──────▼───────┐
         │  FastAPI API  │   │  MCP Server  │
         │  (qxm/api/)   │   │  (qxm/mcp/)  │
         └───────┬──────┘   └──────┬───────┘
                 │                  │
         ┌───────▼──────────────────▼──────┐
         │        Core Engine Layer         │
         │                                  │
         │  MatchingEngine  ←→  OrderBook  │
         │       ↓                          │
         │  PositionManager  ←→  EventBus  │
         │                                  │
         │         (qxm/core/)              │
         └──────┬───────────────────┬──────┘
                │                   │
        ┌───────▼──────┐    ┌──────▼───────┐
        │  Risk Layer   │    │  Data Layer  │
        │               │    │              │
        │  VaREngine    │    │ DataFeed     │
        │  OptionPricer │    │ TimeSeriesDB │
        │  Portfolio    │    │ Transforms   │
        │               │    │              │
        │ (qxm/risk/)   │    │ (qxm/data/) │
        └──────────────┘    └──────────────┘
```

## Module Details

### `qxm/core/` — Core Trading Engine

**models.py** — Domain models using Pydantic v1:
- `Instrument`: Tradeable instrument with tick size, lot size, exchange metadata
- `Order`: Immutable order with computed status property
- `Trade`: Executed fill record
- `Position`: Mutable position with P&L tracking via `apply_fill()`
- `Tick`: High-frequency market data point using `__slots__` for memory efficiency
- `TickSize`: Custom Pydantic type with `__get_validators__()` (v1 pattern)

**book.py** — Order Book:
- FIFO matching at each price level using `collections.deque`
- `SortedDict` from `sortedcontainers` with negated keys for bid-side price priority
- Thread-safe via `threading.RLock`
- `depth_snapshot()` returns top-N levels

**engine.py** — Matching Engine:
- `MatchingEngine`: Processes orders through pre-trade risk checks, then matches
- `PreTradeRiskCheck`: `Protocol` class (structural subtyping) for pluggable risk checks
- `PositionManager`: Tracks positions and unrealised P&L per symbol
- FIFO matching: market orders cross against resting limit orders

**events.py** — Event Sourcing:
- `EventType`: 12 event types (ORDER_SUBMITTED, TRADE_EXECUTED, etc.)
- `DomainEvent`: Frozen dataclass with timestamp, type, and payload
- `EventLog`: Append-only event store with `replay()` for state reconstruction
- `EventBus`: Pub/sub with callback and async generator consumption modes

### `qxm/risk/` — Risk Analytics

**var.py** — Value at Risk:
- Parametric VaR: $VaR = \mu + z_{1-\alpha} \cdot \sigma \cdot \sqrt{t}$
- Historical VaR: Percentile from historical return distribution
- Conditional VaR (CVaR/Expected Shortfall): Mean of losses beyond VaR
- `VaREngine`: Facade for all methods

**greeks.py** — Options Greeks:
- Black-Scholes-Merton pricing: $C = SN(d_1) - Ke^{-rT}N(d_2)$
- `CachedGreek`: Descriptor pattern with `__set_name__`, `__get__` for lazy computation
- Cache invalidation via `_param_hash` — recalculates only when inputs change
- `OptionPricer`: All 5 Greeks (delta, gamma, theta, vega, rho)
- `implied_volatility()`: Newton-Raphson root finding

**portfolio.py** — Portfolio Analytics:
- Operator overloading: `+` (combine), `-` (hedge), `*` (scale)
- Aggregates VaR and Greeks across positions
- `sharpe_ratio()`, `max_drawdown()`, `snapshot()` methods

### `qxm/data/` — Market Data

**feed.py** — Data Generation & Streaming:
- `GBMSimulator`: Geometric Brownian Motion price simulation
- `MarketDataFeed`: Async generator yielding `Tick` objects
- `WebSocketFeedAdapter`: Bridges WebSocket connections to the feed

**store.py** — Persistence:
- SQLAlchemy ORM with SQLite backend
- `TickRecord`, `OHLCRecord`, `TradeRecord` tables
- `TimeSeriesStore`: CRUD with time-range queries

**transform.py** — Data Transformations:
- `ticks_to_ohlc()`: Resample ticks into OHLC bars
- `compute_vwap()`, `compute_twap()`: Volume/time-weighted prices
- `compute_returns()`, `compute_volatility()`: Return series analytics
- `rolling_mean()`, `rolling_std()`, `exponential_moving_average()`

### `qxm/strategy/` — Strategy Framework

**base.py** — Framework Core:
- `StrategyMeta`: Metaclass that auto-registers subclasses into `_registry`
- `BaseStrategy`: Abstract base with `on_tick()`, `on_bar()`, `evaluate()` lifecycle
- `Signal`: Direction + strength + metadata
- `SignalStrength`: Enum (WEAK, MODERATE, STRONG)

**momentum.py** — Momentum Strategies:
- `MomentumBreakout`: Donchian channel breakout
- `EMACrossover`: Dual EMA crossover (fast/slow)

**mean_reversion.py** — Mean Reversion Strategies:
- `BollingerMeanReversion`: Bollinger Band touch reversal
- `StatisticalArbitrage`: Pairs trading with z-score thresholds

### `qxm/auth/` — Authentication

**signing.py** — Request Signing:
- HMAC-SHA256 canonical request signing
- Replay protection via timestamp validation (5-minute window)

**keys.py** — Key Management:
- `KeyManager`: Generate, validate, revoke, rotate API keys
- Key storage in memory (production would use a vault)

### `qxm/api/` — REST API

**routes.py** — FastAPI Endpoints:
- `POST /api/orders` — Submit orders
- `GET /api/positions` — Get positions
- `GET /api/risk` — Get risk metrics
- `GET /api/instruments/search` — Search instruments
- `GET /api/dashboard` — Dashboard data (Challenge 7)

**middleware.py** — Middleware Stack:
- `APIKeyAuthMiddleware`: API key authentication
- `RequestLoggingMiddleware`: Request/response logging

### `qxm/mcp_server/` — MCP Integration

**server.py** — Model Context Protocol Server:
- 8 tools for AI assistant integration
- stdio transport for VS Code
- Tools: submit_order, cancel_order, get_positions, get_risk_metrics, get_portfolio_snapshot, list_instruments, list_strategies, get_order_book

## Design Patterns

| Pattern | Location | Purpose |
|---------|----------|---------|
| Metaclass | `strategy/base.py` | Auto-register strategy classes |
| Descriptor | `risk/greeks.py` | Cache expensive computations |
| Protocol (structural typing) | `core/engine.py` | Pluggable risk checks |
| Event Sourcing | `core/events.py` | Audit trail, state replay |
| `__slots__` | `core/models.py` | Memory efficiency for Tick |
| Operator overloading | `risk/portfolio.py` | Portfolio algebra |
| Async Generator | `data/feed.py` | Streaming market data |
| Factory | `main.py` | FastAPI app construction |
| Decorator | `utils/decorators.py` | Timing, retry, rate limiting |

## Data Flow

```
GBMSimulator
    → MarketDataFeed.stream() [async generator]
    → MatchingEngine.submit_order()
    → OrderBook._match() [FIFO at price level]
    → Trade created
    → EventBus.publish(TRADE_EXECUTED)
    → PositionManager.apply_fill() [updates P&L]
    → PortfolioAnalytics [VaR + Greeks aggregation]
    → API/MCP Server [serves to clients]
```

## Dependencies

- **pydantic** (v1): Domain model validation
- **fastapi + uvicorn**: REST API server
- **sqlalchemy**: ORM for time-series storage
- **sortedcontainers**: Efficient sorted data structures for order book
- **scipy + numpy**: Statistical distributions, BSM formulas
- **websockets**: WebSocket market data adapter
- **mcp**: Model Context Protocol SDK
- **pyyaml**: Configuration parsing
