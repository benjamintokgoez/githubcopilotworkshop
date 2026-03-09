# Copilot Instructions — QuantCore

## Project Overview

This is **QuantCore** (`qxm`), a quantitative trading engine written in Python 3.11+. It simulates order matching, risk analytics, and portfolio management for educational purposes.

## Key Architecture

- **qxm/core/**: Domain models (Pydantic v1), order book (SortedDict + FIFO deque), matching engine (FIFO), event sourcing (EventBus/EventLog)
- **qxm/risk/**: Value at Risk (parametric/historical/CVaR), Black-Scholes Greeks with descriptor caching, portfolio analytics with operator overloading
- **qxm/data/**: GBM-simulated async market data feed, SQLAlchemy time-series store, OHLC/VWAP transforms
- **qxm/strategy/**: Metaclass-based strategy framework with auto-registration, momentum and mean-reversion implementations
- **qxm/auth/**: HMAC-SHA256 request signing, API key lifecycle management
- **qxm/api/**: FastAPI REST API with authentication middleware
- **qxm/mcp_server/**: Model Context Protocol server with trading tools
- **qxm/utils/**: JSON serialisation, decorators (timed/retry/rate-limit), Prometheus-style metrics

## Important Patterns

- **Pydantic v1** is used throughout (`@validator`, `class Config:`, `.dict()`, `__get_validators__`, `update_forward_refs()`) — not v2
- **StrategyMeta** metaclass in `strategy/base.py` auto-registers any `BaseStrategy` subclass into `_registry`
- **CachedGreek** descriptor in `risk/greeks.py` caches expensive BSM calculations, invalidating when `_param_hash` changes
- **PreTradeRiskCheck** is a `Protocol` class (structural subtyping) in `core/engine.py`
- **Tick** uses `__slots__` for memory efficiency
- **PortfolioAnalytics** overloads `+`, `-`, `*` operators for portfolio algebra
- **EventBus** supports both callback and async generator consumption

## Financial Domain Context

- **Order Book**: Bids sorted descending (negated keys in SortedDict), asks sorted ascending
- **Matching**: FIFO at each price level; market orders cross at resting price
- **VaR**: Measures potential portfolio loss at a given confidence level
- **Greeks**: Delta, gamma, theta, vega, rho — option price sensitivities
- **BSM**: Black-Scholes-Merton option pricing model

## Configuration

- `settings.yaml`: Server and application configuration
- `instruments.json`: Tradeable instrument definitions
- `pyproject.toml`: Project metadata, dependencies, tool configs

## Testing

- Tests in `tests/` using pytest
- Fixtures in `tests/conftest.py`
- Run with: `pytest tests/ -v`

## When Generating Code

- Follow existing naming conventions (see CONTRIBUTING.md)
- Use type hints on all public functions
- New strategies should subclass `BaseStrategy` — metaclass handles registration
- New MCP tools should follow the `@mcp.tool()` decorator pattern in `mcp_server/server.py`
- API endpoints use FastAPI router pattern in `api/routes.py`
