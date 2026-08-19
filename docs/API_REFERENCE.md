# QuantCore API Reference

QuantCore exposes two local integration surfaces:

1. a FastAPI REST API under `/api/v1`;
2. a Model Context Protocol (MCP) server built with the official Python SDK v2.

Both operate on simulated data. They are workshop interfaces, not production
trading services.

## Shared conventions

| Concern | Contract |
|---|---|
| Authentication | REST uses `X-API-Key`; MCP binds identity when the server is constructed |
| Client identity | Derived from trusted server configuration, never from request or tool arguments |
| Money and quantity | Exact decimal strings in JSON and MCP results |
| Time | Aware ISO 8601 UTC timestamps, normally ending in `Z` |
| Order matching | FIFO within each price level; the resting maker price wins |
| Risk sign | VaR and CVaR are non-negative loss magnitudes |
| Data | Deterministic or simulated; no live-market claim |
| Currency | Instrument and reporting labels are explicit; QuantCore performs no FX conversion |

The domain uses the American field names `symbol`, `side`, `price`, and
`quantity` in every locale. The dashboard localizes presentation, not payload
identifiers.

## REST API

The default local base URL is:

```text
http://127.0.0.1:8443/api/v1
```

Start the local server from an installed development checkout with:

```bash
python main.py --host 127.0.0.1 --port 8443
```

Set `QXM_API_KEY` in the process environment first if you need protected
routes; otherwise the server deliberately starts with no valid key. QuantCore
does not auto-load `.env`. The default local server is HTTP even though it uses
port 8443; the simulator does not configure TLS.

Interactive schemas are available at `/docs`, `/redoc`, and `/openapi.json`.

### Runtime configuration

`settings.yaml` is fail-closed: unknown sections/keys, malformed types, an
unsupported feed mode, non-positive/non-finite intervals, and invalid currency
codes stop application construction. The supported surface is:

| Section | Implemented keys |
|---|---|
| `timezone` | Fixed contract: `application: UTC`, `presentation: Europe/Berlin` |
| `server` | `host`, `port`, `log_level`, `cors_origins`, `cors_allow_credentials` |
| `database` | `url`, `echo` |
| `feed` | `mode`, positive `interval_ms`, bounded integer `seed` |
| `risk` | Optional positive finite `daily_volatility`; `null` keeps VaR unavailable |
| `dashboard` | Three-letter aggregate reporting `currency` |
| `auth` | Optional positive `key_ttl_seconds` |
| `logging` | `level`, `format` |

The application supports the deterministic `simulated` feed and explicit
`disabled`/`off`/`none` modes. `websocket` is deliberately rejected: the
reconnecting adapter is a reusable library surface, but no live venue is wired
into this offline workshop app.

Secrets and bootstrap identity are environment-only:
`QXM_AUTH_SECRET_KEY`, `QXM_API_KEY`, and `QXM_API_CLIENT_ID`. See
`.env.example`; QuantCore does not load that file automatically. `X-API-Key` is
a fixed protocol header, not a configurable setting.

### Authentication and permissions

Send the raw bootstrap or managed API key in every protected request:

```http
X-API-Key: qxm_...
```

Keys carry one or more permissions:

| Permission | Access |
|---|---|
| `read` | Orders, positions, portfolio, instruments, strategies, metrics, dashboard |
| `trade` | Submit and cancel orders |
| `admin` | Key-management capability in the auth library; no REST key-management route |

Missing keys return `401`. Invalid, expired, or revoked keys return `403`.
Authenticating one client never grants access to another client's orders or
positions.

Public routes:

- `GET /`
- `GET /api/v1/health`
- `GET /docs`
- `GET /redoc`
- `GET /openapi.json`

All other routes below require `X-API-Key`.

### Endpoint summary

| Method | Path | Permission | Purpose |
|---|---|---|---|
| `GET` | `/health` | Public | Liveness and simulation mode |
| `POST` | `/orders` | `trade` | Submit an order |
| `GET` | `/orders` | `read` | List the caller's orders |
| `GET` | `/orders/{order_id}` | `read` | Read one caller-owned order |
| `DELETE` | `/orders/{order_id}` | `trade` | Cancel a caller-owned resting order |
| `GET` | `/positions` | `read` | List the caller's positions |
| `GET` | `/portfolio/snapshot` | `read` | Current portfolio snapshot |
| `GET` | `/portfolio/risk` | `read` | Current risk analytics |
| `GET` | `/instruments/search` | `read` | Bounded instrument search |
| `GET` | `/strategies` | `read` | Registered strategy names |
| `GET` | `/metrics` | `read` | Process metrics snapshot |
| `GET` | `/dashboard` | `read` | Aggregate dashboard payload |

### Health

```http
GET /api/v1/health
```

```json
{
  "status": "healthy",
  "version": "0.5.0",
  "timestamp": "2026-08-19T08:00:00Z",
  "mode": "simulation",
  "feed": "running"
}
```

The health route is a liveness response, not proof of production readiness,
external-market connectivity, or persistence durability. `feed` is `running`,
`off`, or `stopped`; an unexpectedly stopped configured feed changes `status`
to `degraded` without exposing failure details.

### Submit an order

```http
POST /api/v1/orders
Content-Type: application/json
X-API-Key: qxm_...
```

```json
{
  "order_id": "lab1-buy-001",
  "symbol": "SAP",
  "side": "BUY",
  "order_type": "LIMIT",
  "quantity": "10",
  "price": "125.40",
  "time_in_force": "GTC"
}
```

Request fields:

| Field | Required | Notes |
|---|---|---|
| `order_id` | No | Generated when omitted; otherwise 1-64 URL-safe characters and not `.` or `..` |
| `symbol` | Yes | Must exist in the configured instrument catalogue |
| `side` | Yes | `BUY` or `SELL` |
| `order_type` | No | `LIMIT` by default; also represents `MARKET`, `STOP`, and `STOP_LIMIT` |
| `quantity` | Yes | Positive decimal and a valid instrument lot multiple |
| `price` | Conditional | Required for `LIMIT`; must follow tick size |
| `stop_price` | Conditional | Represented by the model, but stop orders are not implemented |
| `time_in_force` | No | `GTC` by default; `IOC` and `FOK` are implemented |
`client_id`, status, fill quantity, timestamps, metadata, and trades are
server-owned and
must not appear in the request body.

A successful engine submission returns `201`, even when an accepted `IOC` or
`FOK` ends in `CANCELLED`:

```json
{
  "accepted": true,
  "order_id": "lab1-buy-001",
  "status": "ACCEPTED",
  "filled_quantity": "0",
  "order": {
    "order_id": "lab1-buy-001",
    "client_id": "workshop-client",
    "symbol": "SAP",
    "side": "BUY",
    "order_type": "LIMIT",
    "quantity": "10",
    "price": "125.40",
    "status": "ACCEPTED",
    "filled_quantity": "0"
  },
  "trades": []
}
```

The complete `order` and `trade` records include aware UTC timestamps. Use the
generated OpenAPI schema for their full field list.

Important lifecycle rules:

- IDs are reserved before asynchronous matching begins and are never reusable,
  including after rejection.
- Resting liquidity determines the execution price.
- `MARKET` and `IOC` remainders finish `CANCELLED`.
- An unfillable `FOK` is accepted and then cancelled without consuming
  liquidity.
- `STOP`, `STOP_LIMIT`, `DAY`, and `GTD` are represented for migration
  exercises but rejected by the matching engine.

Common outcomes:

| Status | Meaning |
|---|---|
| `400` | Domain-invalid request or intentional engine rejection |
| `401` | Missing API key |
| `403` | Invalid key or insufficient permission |
| `409` | Duplicate order ID |
| `422` | HTTP/schema validation failure |
| `500` | Execution occurred but resulting trades could not be persisted |

A persistence failure is deliberately truthful:

```json
{
  "detail": {
    "error": "trade_persistence_failed",
    "order_id": "lab1-buy-001",
    "status": "FILLED",
    "filled_quantity": "10",
    "trade_ids": ["..."],
    "message": "The order executed and the in-memory engine state is authoritative, but the resulting trades could not be persisted. Reconcile from the engine trade log; do not resubmit this order."
  }
}
```

Matching and database persistence are not one atomic transaction. Do not
resubmit after this response.

### List and read orders

```http
GET /api/v1/orders
GET /api/v1/orders/lab1-buy-001
X-API-Key: qxm_...
```

The list response is:

```json
{
  "orders": [],
  "count": 0
}
```

Only orders submitted through the REST service by the authenticated client are
listed. Another client's order ID is returned as `404`, not disclosed.

### Cancel an order

```http
DELETE /api/v1/orders/lab1-buy-001
X-API-Key: qxm_...
```

A resting order returns its updated `CANCELLED` representation. Unknown orders
return `404`; known orders that are already filled, rejected, or cancelled
return `409`.

### Positions

```http
GET /api/v1/positions
X-API-Key: qxm_...
```

```json
{
  "client_id": "workshop-client",
  "positions": [
    {
      "client_id": "workshop-client",
      "symbol": "SAP",
      "currency": "EUR",
      "quantity": "10",
      "average_entry_price": "125.40",
      "last_price": "126.00",
      "realized_pnl": "0",
      "unrealized_pnl": "6.00",
      "last_updated": "2026-08-19T08:00:00Z"
    }
  ],
  "count": 1
}
```

Feed ticks mark open positions when the simulated feed is enabled.

### Portfolio snapshot

```http
GET /api/v1/portfolio/snapshot
X-API-Key: qxm_...
```

The snapshot includes the caller's positions, cash balance, market value, total
value, realized P&L, unrealized P&L, and an aware UTC `timestamp`. Decimal
values remain strings.

Portfolio arithmetic does not perform currency conversion. Do not interpret a
raw total across unlike instrument currencies as a converted economic value.

### Portfolio risk

```http
GET /api/v1/portfolio/risk
X-API-Key: qxm_...
```

```json
{
  "var_95": null,
  "var_99": null,
  "gross_exposure": "1254.00",
  "sharpe_ratio": null,
  "max_drawdown": null,
  "greeks": {
    "delta": "0.0",
    "gamma": "0.0",
    "theta": "0.0",
    "vega": "0.0",
    "rho": "0.0"
  }
}
```

`var_95` and `var_99` are `null` when no daily-volatility assumption is
configured. QuantCore does not invent market history or a volatility estimate.
When present, VaR values are non-negative potential-loss magnitudes.

### Search instruments

```http
GET /api/v1/instruments/search?q=SAP&limit=20
X-API-Key: qxm_...
```

`q` is trimmed, must contain a non-whitespace character, and is limited to 64
characters. `limit` is from 1 through 100. The response contains `query`,
`results`, and `count`; each result includes symbol, name, asset class,
currency, tick size, lot size, and trading status.

Database-backed search uses parameterized predicates. SQL wildcard and quote
characters are data, not executable SQL.

### Strategies

```http
GET /api/v1/strategies
X-API-Key: qxm_...
```

Returns the names registered by `StrategyMeta`:

```json
{
  "strategies": [
    "BollingerMeanReversion",
    "EMACrossover",
    "MomentumBreakout",
    "StatisticalArbitrage"
  ]
}
```

This route reports registrations; it does not start a strategy.

### Metrics

```http
GET /api/v1/metrics
X-API-Key: qxm_...
```

Returns a point-in-time JSON object with `counters`, `gauges`, and
`histograms`. It is a process-local teaching surface, not a hosted telemetry
export. QuantCore sends no workshop telemetry to an external service.

### Dashboard data

```http
GET /api/v1/dashboard
X-API-Key: qxm_...
```

The top-level shape is stable:

```json
{
  "as_of": "2026-08-19T08:00:00Z",
  "currency": "EUR",
  "kpis": {},
  "positions": [],
  "pnl_history": [],
  "risk": {},
  "order_books": {}
}
```

Empty arrays and unavailable risk values are valid states. Top-level `currency`
labels nominal aggregate totals; mixed-currency values are not converted. Each
position also carries its instrument currency so row-level prices and P&L are
not mislabeled.

The static bilingual dashboard shell is served at `/` and `/api/v1/dashboard`
is its authenticated data source. The API key is kept in memory or
`sessionStorage` for the current browser tab only.

### Error format

FastAPI validation errors use the standard `detail` array. Domain errors use a
structured `detail` object:

```json
{
  "detail": {
    "error": "order_rejected",
    "order_id": "lab1-buy-001",
    "status": "REJECTED",
    "reason": "..."
  }
}
```

Do not parse human-readable `reason` or `message` text as a stable machine
code. Use the `error` field and HTTP status.

### CORS

CORS is disabled unless origins are explicitly configured. Do not use `*` with
credentials. Middleware ordering ensures configured CORS headers also appear
on authentication failures.

## MCP server

QuantCore uses the official stable MCP Python SDK v2:

```text
mcp>=2,<3
```

The server entry point is:

```bash
quantcore-mcp
```

or:

```bash
python -m qxm.mcp_server.server
```

The default transport is stdio. Standard output is reserved for MCP protocol
traffic; diagnostics belong on standard error.

### MCP security model

The default server is read-only. Write tools exist only when the host creates
the server with both:

```python
create_mcp_server(
    allow_writes=True,
    client_id="workshop-client",
)
```

API keys and client IDs are not MCP tool arguments. Tool annotations describe
intent to compatible clients but are not an authorization boundary.

### Read-only tools

| Tool | Purpose |
|---|---|
| `list_instruments` | Return the configured simulated instrument catalogue |
| `get_order_book` | Return bounded depth for one symbol |
| `calculate_risk` | Compute bounded educational risk analytics |

### Optional write tools

| Tool | Purpose |
|---|---|
| `submit_order` | Submit a bounded order for the construction-time client |
| `cancel_order` | Cancel that client's resting order |

Write quantity is capped at 10,000 units. Submission results bound serialized
trade detail to 100 records and report `trade_count`,
`returned_trade_count`, and `trades_truncated` without hiding execution. Rejected
submissions carry the simulation engine's actionable `rejection_reason`, bounded
to 256 characters at the MCP boundary.

### MCP host configuration

For current VS Code clients, a stdio server entry in `.vscode/mcp.json` uses
host fields such as `type`, `command`, `args`, `cwd`, `env`, and `envFile`.
Optional sandbox configuration uses supported filesystem and network policy
fields. Tool selection and ordinary approval are client controls outside
`mcp.json`; server tool annotations are metadata. Current VS Code auto-approves
tool calls for a server with `sandboxEnabled: true`, so the sandbox rules and
their platform limitations become the approval boundary.

The deterministic `elective-mcp` scenario contains the workshop's current,
inert configuration fixture. Do not place a real credential in committed MCP
configuration.

## Source of truth

- REST schema: `/openapi.json`
- REST routes: `qxm/api/routes.py`
- REST request/response models: `qxm/api/schemas.py`
- MCP registration and bounds: `qxm/mcp_server/server.py`
- Domain invariants: `qxm/core/models.py` and `qxm/core/engine.py`

When prose and generated OpenAPI details differ, treat the running
implementation and its tests as the executable contract and correct the
documentation in the same change.
