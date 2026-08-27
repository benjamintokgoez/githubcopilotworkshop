# MittelWerk API reference

MittelWerk exposes two local integration surfaces:

1. a FastAPI REST API under `/api/v1`;
2. a Model Context Protocol (MCP) server built with the official Python SDK v2.

Both operate only on synthetic workshop data. They are not connected to real
equipment, providers, organisations, or site systems.

## Shared conventions

| Concern | Contract |
|---|---|
| Authentication | REST uses `X-API-Key`; MCP binds identity when its server is constructed |
| Organisation identity | Derived from trusted key or server configuration, never a work-order or tool argument |
| Hours, rates, and costs | `Decimal` in the domain; exact decimal strings at JSON and MCP boundaries |
| Time | Aware ISO 8601 UTC timestamps |
| Dispatch | Rate priority, FIFO at equal rates, and the resting work order's rate |
| Backlog risk | Non-negative hour magnitudes |
| Currency | Asset and reporting labels are explicit; no FX conversion is performed |
| Data | Deterministic or synthetic; no connection to a live site |

Field names such as `asset_id`, `requested_hours`, and `max_hourly_rate` stay
the same in every locale. The dashboard localises presentation, not machine
payload identifiers.

## REST API

The default local base URL is:

```text
http://127.0.0.1:8443/api/v1
```

Start the server from an installed development checkout:

```bash
python main.py --host 127.0.0.1 --port 8443
```

Set `MITTELWERK_API_KEY` before starting if protected routes are needed. The
application does not auto-load `.env`; without a bootstrap key it deliberately
starts with no valid credentials. Port `8443` uses HTTP in this local
simulation; TLS is not configured.

Interactive schemas are available at `/docs`, `/redoc`, and `/openapi.json`.

### Runtime configuration

`settings.yaml` is fail-closed. Unknown sections or keys, malformed types,
unsupported feed modes, non-positive intervals, and invalid currency codes
stop application construction.

| Section | Implemented keys |
|---|---|
| `timezone` | Fixed contract: `application: UTC`, `presentation: Europe/Berlin` |
| `server` | `host`, `port`, `log_level`, `cors_origins`, `cors_allow_credentials` |
| `database` | `url`, `echo` |
| `feed` | `mode`, positive `interval_ms`, bounded integer `seed` |
| `risk` | Optional positive finite `hours_volatility`; `null` keeps parametric backlog risk unavailable |
| `dashboard` | Three-letter aggregate reporting `currency` |
| `auth` | Optional positive `key_ttl_seconds` |
| `logging` | `level`, `format` |

The application supports `simulated` and explicit `disabled`/`off`/`none`
feed modes. `websocket` is rejected because no site gateway is wired into the
offline workshop application.

Secrets and bootstrap identity are environment-only:

- `MITTELWERK_AUTH_SECRET_KEY`
- `MITTELWERK_API_KEY`
- `MITTELWERK_API_ORGANIZATION_ID`

See `.env.example`. `X-API-Key` is a fixed protocol header, not a configurable
setting.

### Authentication and permissions

Send the raw bootstrap or managed API key with each protected request:

```http
X-API-Key: mwk_...
```

| Permission | Access |
|---|---|
| `read` | Work orders, workloads, organisation analytics, equipment, policies, metrics, and dashboard |
| `dispatch` | Submit and cancel work orders |
| `admin` | Key lifecycle operations in the auth library; no REST administration route |

A missing key returns `401`. An invalid, expired, revoked, or
under-permissioned key returns `403`. One organisation cannot read or cancel
another organisation's work orders.

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
| `GET` | `/health` | Public | Liveness, simulation mode, and feed state |
| `POST` | `/work-orders` | `dispatch` | Submit a request or provider capacity offer |
| `GET` | `/work-orders` | `read` | List the caller's work orders |
| `GET` | `/work-orders/{work_order_id}` | `read` | Read one caller-owned work order |
| `DELETE` | `/work-orders/{work_order_id}` | `dispatch` | Cancel a caller-owned resting work order |
| `GET` | `/workloads` | `read` | List the caller's signed asset workloads |
| `GET` | `/organization/snapshot` | `read` | Current organisation snapshot |
| `GET` | `/organization/risk` | `read` | Current operational analytics |
| `GET` | `/equipment/search` | `read` | Bounded equipment search |
| `GET` | `/dispatch-policies` | `read` | Registered policy names |
| `GET` | `/metrics` | `read` | Process metrics snapshot |
| `GET` | `/dashboard` | `read` | Aggregate dashboard payload |

Paths in this section are relative to `/api/v1`.

### Health

```http
GET /api/v1/health
```

```json
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": "2026-08-19T08:00:00Z",
  "mode": "simulation",
  "feed": "running"
}
```

`feed` is `running`, `off`, or `stopped`. If a configured feed stops
unexpectedly, `status` becomes `degraded`; failure details remain in server
logs rather than the public response.

### Submit a work order

```http
POST /api/v1/work-orders
Content-Type: application/json
X-API-Key: mwk_...
```

Provider capacity offer:

```json
{
  "work_order_id": "provider-offer-001",
  "asset_id": "PRESS-04",
  "side": "OFFER",
  "mode": "RATE_CAPPED",
  "requested_hours": "8.0",
  "max_hourly_rate": "110.00",
  "dispatch_window": "OPEN"
}
```

Organisation service request:

```json
{
  "work_order_id": "service-request-001",
  "asset_id": "PRESS-04",
  "side": "REQUEST",
  "mode": "RATE_CAPPED",
  "requested_hours": "4.0",
  "max_hourly_rate": "118.00",
  "priority": 2,
  "dispatch_window": "IMMEDIATE"
}
```

| Field | Required | Notes |
|---|---|---|
| `work_order_id` | No | Generated when omitted; otherwise 1-64 path-safe characters and not `.` or `..` |
| `asset_id` | Yes | Must exist in `equipment.json` |
| `side` | Yes | `REQUEST` or `OFFER` |
| `requested_hours` | Yes | Positive decimal and a valid asset hour-lot multiple |
| `mode` | No | `RATE_CAPPED` by default; `ANY_RATE` is also implemented |
| `max_hourly_rate` | Conditional | Required for `RATE_CAPPED`; must follow the asset rate increment |
| `escalation_rate` | Conditional | Represented by the model; escalation modes are not implemented |
| `priority` | No | Integer from 1 through 5 |
| `dispatch_window` | No | `OPEN` by default; `IMMEDIATE` and `COMPLETE` are implemented |

`organization_id`, status, assigned hours, average service rate, timestamps,
and assignments are server-owned and must not appear in the request body.

A successful submission returns `201`:

```json
{
  "accepted": true,
  "work_order_id": "service-request-001",
  "status": "ASSIGNED",
  "assigned_hours": "4.0",
  "work_order": {
    "work_order_id": "service-request-001",
    "organization_id": "workshop-operations",
    "asset_id": "PRESS-04",
    "side": "REQUEST",
    "mode": "RATE_CAPPED",
    "requested_hours": "4.0",
    "max_hourly_rate": "118.00",
    "status": "ASSIGNED",
    "assigned_hours": "4.0",
    "average_service_rate": "110.00"
  },
  "assignments": [
    {
      "asset_id": "PRESS-04",
      "hourly_rate": "110.00",
      "hours": "4.0"
    }
  ]
}
```

The complete records include aware UTC timestamps and both requester and
provider identifiers. Use OpenAPI for the full generated schema.

Important lifecycle rules:

- An ID is reserved before asynchronous dispatch and is never reusable,
  including after rejection.
- Eligible provider offers are considered from lowest rate to highest, FIFO
  within one rate.
- An assignment uses the resting work order's rate, not the incoming request's
  ceiling.
- An `ANY_RATE` or `IMMEDIATE` remainder stands down.
- An unfulfillable `COMPLETE` work order consumes no capacity.
- `ESCALATION`, `ESCALATION_CAPPED`, `SHIFT`, and `SCHEDULED_END` are
  represented but rejected because their trigger or scheduling subsystems do
  not exist.

| Status | Meaning |
|---|---|
| `400` | Domain-invalid request or explicit engine rejection |
| `401` | Missing API key |
| `403` | Invalid key or insufficient permission |
| `409` | Duplicate work-order ID |
| `422` | HTTP or schema validation failure |
| `500` | Dispatch occurred but assignments could not be persisted |

A persistence failure is deliberately truthful:

```json
{
  "detail": {
    "error": "assignment_persistence_failed",
    "work_order_id": "service-request-001",
    "status": "ASSIGNED",
    "assigned_hours": "4.0",
    "assignment_ids": ["..."],
    "message": "The work order executed and the in-memory engine state is authoritative, but the resulting assignments could not be persisted. Reconcile from the engine assignment log; do not resubmit this work order."
  }
}
```

Dispatch and storage are not one atomic transaction. Do not resubmit after this
response.

### List, read, and cancel work orders

```http
GET /api/v1/work-orders
GET /api/v1/work-orders/service-request-001
DELETE /api/v1/work-orders/service-request-001
X-API-Key: mwk_...
```

The list response contains `work_orders` and `count`. Only work orders
submitted through REST by the authenticated organisation are visible. Another
organisation's ID returns `404`, not a disclosure. Cancelling a resting work
order returns its `CANCELLED` representation; a known terminal work order
returns `409`.

### Workloads

```http
GET /api/v1/workloads
X-API-Key: mwk_...
```

```json
{
  "organization_id": "workshop-operations",
  "workloads": [
    {
      "asset_id": "PRESS-04",
      "net_hours": "4.0",
      "average_service_rate": "110.00",
      "realized_cost": "0",
      "unrealized_cost": "0",
      "currency": "EUR"
    }
  ],
  "count": 1
}
```

Positive and negative signed hours distinguish requester and provider
workloads. Costs and reference rates retain exact decimal representation.

### Organisation snapshot and risk

```http
GET /api/v1/organization/snapshot
GET /api/v1/organization/risk
X-API-Key: mwk_...
```

The snapshot contains the organisation ID, workloads, budget balance, total
cost fields, and an aware UTC timestamp.

The risk response includes:

- `backlog_risk_95` and `backlog_risk_99`;
- `utilization_rate`;
- `sla_compliance_rate`;
- `average_lead_time_hours`;
- `service_level_ratio`;
- `max_backlog_overrun`;
- `gross_committed_hours`;
- `computed_at`.

Parametric backlog-risk fields are `null` when `risk.hours_volatility` is
unset. MittelWerk does not invent an operational variability assumption.

### Search equipment

```http
GET /api/v1/equipment/search?q=PRESS&limit=20
X-API-Key: mwk_...
```

`q` is trimmed, must contain a non-whitespace character, and is limited to 64
characters. `limit` is from 1 through 100. Results include asset ID, name,
equipment type, currency, site, hourly service rate, rate increment, and hour
lot size.

Database search uses parameterised predicates and treats SQL wildcard
characters as literal input. The in-memory fallback has the same boundary
behaviour.

### Dispatch policies

```http
GET /api/v1/dispatch-policies
X-API-Key: mwk_...
```

Returns names registered by `DispatchPolicyMeta`, including capacity,
telemetry trend, band-deviation, and cross-asset telemetry policies. Listing a
policy does not execute it or submit a work order.

### Metrics

```http
GET /api/v1/metrics
X-API-Key: mwk_...
```

Returns process-local `counters`, `gauges`, and `histograms`. MittelWerk sends
no workshop telemetry to an external service.

### Dashboard data

```http
GET /api/v1/dashboard
X-API-Key: mwk_...
```

The response always contains:

```json
{
  "as_of": "2026-08-19T08:00:00Z",
  "currency": "EUR",
  "kpis": {},
  "workloads": [],
  "cost_history": [],
  "risk": {},
  "dispatch_queues": {}
}
```

Empty collections are a valid initial state. `currency` labels nominal
aggregate simulator values; no conversion between EUR and CHF occurs.

## MCP server

MittelWerk uses the official Python SDK v2:

```python
from mcp.server import MCPServer
```

Run the default read-only stdio server:

```bash
mittelwerk-mcp
# or
python -m mittelwerk.mcp_server.server
```

Do not print application text to stdout from this process; stdout carries MCP
protocol traffic.

### Construction and authorisation

The default server is read-only:

```python
server = create_mcp_server(engine, equipment)
```

Write tools require explicit construction-time opt-in and a bound identity:

```python
server = create_mcp_server(
    engine,
    equipment,
    allow_writes=True,
    organization_id="workshop-operations",
)
```

Tool annotations are hints for clients and models. They do not grant
authorisation. Registration plus the bound organisation identity is the
enforcement boundary. Identity is never accepted as a tool argument.

### Default read-only tools

| Tool | Bounds and result |
|---|---|
| `list_equipment` | `limit` 1-50, bounded offset; returns deterministic asset order |
| `get_dispatch_queue` | Known asset, depth 1-20; returns request/offer levels and summary rates |
| `calculate_service_risk` | Caller-supplied backlog values; at most 256 observations and a 1-365-day horizon |

`calculate_service_risk` requires `hours_volatility`, `backlog_history`, or
both. It returns non-negative parametric, historical, and conditional
backlog-risk magnitudes only for the inputs supplied.

### Opt-in write tools

| Tool | Contract |
|---|---|
| `submit_work_order` | Submit up to 10,000 hours for the construction-time organisation |
| `cancel_work_order` | Cancel an open work order created by that same MCP server identity |

MCP write mode supports `RATE_CAPPED`/`ANY_RATE` and
`OPEN`/`IMMEDIATE`/`COMPLETE`. Results retain at most 100 assignments while
reporting total and returned counts and whether the list was truncated.
Rejection reasons are bounded to 256 characters.

The MCP server has no network or real-equipment capability. Confirmation and
sandbox settings in a client remain separate controls; they do not replace
server authorisation.

## Source locations

- Application factory and configuration: `main.py`
- REST routes: `mittelwerk/api/routes.py`
- REST request/response models: `mittelwerk/api/schemas.py`
- Authentication: `mittelwerk/auth/`
- MCP registration and bounds: `mittelwerk/mcp_server/server.py`
- Domain invariants: `mittelwerk/core/models.py` and
  `mittelwerk/core/engine.py`
- Persistence: `mittelwerk/telemetry/store.py`
