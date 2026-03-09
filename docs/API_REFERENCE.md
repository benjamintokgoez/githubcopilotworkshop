# API Reference — QuantCore

## REST API

Base URL: `http://localhost:8443`

### Authentication

All endpoints (except health check) require an API key in the `X-API-Key` header:

```
X-API-Key: your-api-key-here
```

---

### Orders

#### Submit Order

```
POST /api/orders
```

**Request Body:**
```json
{
  "symbol": "AAPL",
  "side": "BUY",
  "order_type": "LIMIT",
  "quantity": 100,
  "price": 150.25,
  "client_id": "client-001",
  "time_in_force": "GTC"
}
```

**Parameters:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `symbol` | string | Yes | Instrument symbol |
| `side` | string | Yes | `BUY` or `SELL` |
| `order_type` | string | Yes | `MARKET` or `LIMIT` |
| `quantity` | integer | Yes | Number of units |
| `price` | float | No | Required for LIMIT orders |
| `client_id` | string | Yes | Client identifier |
| `time_in_force` | string | No | `GTC`, `IOC`, `FOK`, `DAY` (default: `GTC`) |

**Response (201):**
```json
{
  "order_id": "ord-abc123",
  "symbol": "AAPL",
  "side": "BUY",
  "status": "NEW",
  "quantity": 100,
  "filled_quantity": 0
}
```

#### Cancel Order

```
DELETE /api/orders/{order_id}
```

**Response (200):**
```json
{
  "order_id": "ord-abc123",
  "status": "CANCELLED"
}
```

---

### Positions

#### Get All Positions

```
GET /api/positions
```

**Response (200):**
```json
{
  "positions": [
    {
      "symbol": "AAPL",
      "quantity": 100,
      "average_price": 150.25,
      "unrealised_pnl": 475.00,
      "realised_pnl": 0.00
    }
  ]
}
```

---

### Risk

#### Get Risk Metrics

```
GET /api/risk
```

**Response (200):**
```json
{
  "portfolio_value": 15025.00,
  "var_95": -1250.50,
  "var_99": -2100.75,
  "total_delta": 0.62,
  "total_gamma": 0.019,
  "sharpe_ratio": 1.45
}
```

---

### Instruments

#### Search Instruments

```
GET /api/instruments/search?q=AAPL
```

**Query Parameters:**
| Param | Type | Description |
|-------|------|-------------|
| `q` | string | Search term to filter instruments |

**Response (200):**
```json
{
  "instruments": [
    {
      "symbol": "AAPL",
      "name": "Apple Inc.",
      "instrument_type": "EQUITY",
      "exchange": "NASDAQ",
      "tick_size": 0.01,
      "lot_size": 1
    }
  ]
}
```

---

### Dashboard

#### Get Dashboard Data

```
GET /api/dashboard
```

**Response (200):**
```json
{
  "kpis": {
    "total_pnl": 12500.00,
    "portfolio_var": -45000.00,
    "active_positions": 5,
    "open_orders": 12
  },
  "positions": [...],
  "price_history": {
    "AAPL": {
      "timestamps": ["2024-01-01T09:30:00", ...],
      "prices": [150.0, 150.5, ...]
    }
  },
  "order_book": {
    "bids": [{"price": 154.90, "quantity": 500}],
    "asks": [{"price": 155.10, "quantity": 300}]
  }
}
```

---

## MCP Server

The MCP server runs over stdio and provides the following tools:

### Existing Tools

| Tool | Description | Key Parameters |
|------|-------------|----------------|
| `submit_order` | Submit a new order | symbol, side, order_type, quantity, price |
| `cancel_order` | Cancel an existing order | order_id |
| `get_positions` | Get all current positions | — |
| `get_risk_metrics` | Get portfolio risk metrics | — |
| `get_portfolio_snapshot` | Get complete portfolio snapshot | — |
| `list_instruments` | List all tradeable instruments | — |
| `list_strategies` | List registered strategies | — |
| `get_order_book` | Get order book for a symbol | symbol, levels |

### Tools Added in Challenge 6

| Tool | Description | Key Parameters |
|------|-------------|----------------|
| `calculate_portfolio_var` | Calculate VaR | confidence_level, time_horizon_days, method |
| `price_option` | BSM option pricing | spot_price, strike_price, time_to_expiry, risk_free_rate, volatility, option_type |
| `get_strategy_signals` | Get strategy signals | symbol, strategy_name |

### Configuration

Add to `.vscode/mcp.json`:
```json
{
  "servers": {
    "quantcore": {
      "command": "python",
      "args": ["-m", "qxm.mcp_server.server"],
      "cwd": "${workspaceFolder}"
    }
  }
}
```

---

## Error Responses

All endpoints return errors in this format:

```json
{
  "detail": "Error description"
}
```

| Status | Meaning |
|--------|---------|
| 400 | Bad request — invalid parameters |
| 401 | Unauthorised — missing or invalid API key |
| 404 | Not found — resource doesn't exist |
| 422 | Validation error — request body failed validation |
| 500 | Internal server error |
